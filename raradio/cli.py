"""CLI orchestration; JSON stdout can be consumed by future interfaces."""

import argparse
import importlib.metadata
import json
import math
import platform
import shutil
import sqlite3
import sys
from contextlib import redirect_stdout
from http.client import HTTPException
from importlib.resources import files
from pathlib import Path
from urllib.request import urlopen

from . import __version__
from .analysis import OllamaAnalyzer, RulesAnalyzer, SingleVoiceAnalyzer
from .project import BookProject, read_source


def _emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _progress(event):
    print(f"Generating {event['segment']} ({event['speaker']}), attempt {event['attempt']}", file=sys.stderr, flush=True)


def _run(project, args):
    # Some model loaders print diagnostics; reserve stdout for the CLI result.
    with redirect_stdout(sys.stderr):
        return project.run(limit=args.limit, max_attempts=args.max_attempts, on_event=_progress)


def _positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _nonnegative_int(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return number


def _positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return number


def _analysis_options(parser):
    parser.add_argument("--analyzer", choices=("ollama", "rules", "single-voice"), default="ollama")
    parser.add_argument("--model", default="qwen3:14b")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--think", choices=("false", "true", "omit", "low", "medium", "high"), default="false")
    parser.add_argument("--timeout", type=_positive_float, default=180)
    parser.add_argument("--batch-size", type=_positive_int, default=24)
    parser.add_argument("--reanalyze", action="store_true", help="Reanalyze automatic annotations while preserving human attributions")


def _analyze(project, args):
    if args.analyzer == "single-voice":
        return project.analyze(SingleVoiceAnalyzer(), reanalyze=args.reanalyze)
    if args.analyzer == "rules":
        return project.analyze(RulesAnalyzer(), reanalyze=args.reanalyze)
    think = {"false": False, "true": True, "omit": None}.get(args.think, args.think)
    analyzer = OllamaAnalyzer(model=args.model, base_url=args.ollama_url, think=think,
                              timeout=args.timeout, batch_size=args.batch_size)
    try:
        return project.analyze(analyzer, reanalyze=args.reanalyze)
    finally:
        try:
            analyzer.unload()
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"Warning: could not unload Ollama model: {exc}", file=sys.stderr)


def _configure(project, filename):
    path = Path(filename).resolve()
    project.configure(json.loads(path.read_text(encoding="utf-8")), base_dir=path.parent)


def _doctor(profile="core", base_url="http://localhost:11434", model="qwen3:14b"):
    """Check selected prerequisites without loading or downloading models."""
    data = {"version": __version__, "profile": profile,
            "python": platform.python_version(), "platform": platform.system(), "architecture": platform.machine(),
            "ffmpeg": shutil.which("ffmpeg"), "ollama": shutil.which("ollama"), "mlx_audio": None,
            "scope": "Dependency preflight only; no model, Metal initialization or speech generation is tested.",
            "checks": []}

    def check(name, ok, detail, hint):
        item = {"name": name, "ok": ok, "detail": detail}
        if not ok:
            item["hint"] = hint
        data["checks"].append(item)

    check("python", sys.version_info >= (3, 11), data["python"], "Use Python 3.11 or later.")
    try:
        import fcntl  # noqa: F401 -- importing is the capability check
        file_locking = True
    except ImportError:
        file_locking = False
    check("file_locking", file_locking, "POSIX fcntl file locking",
          "Use macOS or Linux with POSIX fcntl; native Windows is not supported.")
    try:
        data["mlx_audio"] = importlib.metadata.version("mlx-audio")
    except importlib.metadata.PackageNotFoundError:
        pass
    if profile == "mlx":
        macos = platform.mac_ver()[0] if data["platform"] == "Darwin" else ""
        data["macos"] = macos
        supported = (data["platform"] == "Darwin" and data["architecture"] == "arm64"
                     and bool(macos) and int(macos.split(".")[0]) >= 14)
        check("mlx_platform", supported, f"{data['platform']} {macos} {data['architecture']}",
              "Use an Apple Silicon Mac with macOS 14 or later and Metal GPU access; core workflows also work on Linux.")
        mlx_hint = (
            "From the raradio source checkout run `sh setup.sh mlx`. Expected mlx-audio 0.5.3."
            if supported else
            "MLX speech is only supported on the platform described by the mlx_platform check."
        )
        check("mlx_audio", data["mlx_audio"] == "0.5.3", data["mlx_audio"],
              mlx_hint)
    elif profile == "ollama":
        try:
            # Reuse the analyzer's URL/model validation without making an inference request.
            analyzer = OllamaAnalyzer(base_url=base_url, model=model)
            data["ollama_url"] = analyzer.base_url
            data["model"] = analyzer.model
            with urlopen(analyzer.base_url + "/api/tags", timeout=3) as response:
                payload = json.load(response)
            models = payload.get("models") if isinstance(payload, dict) else None
            if not isinstance(models, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in models
            ):
                raise ValueError("Ollama /api/tags response must contain a models array with model names")
            names = data["ollama_models"] = [item["name"] for item in models]
            check("ollama_server", True, analyzer.base_url, "")
            selected = model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"
            check("ollama_model", selected in names, selected,
                  f"Install the selected model on this Ollama server (for a local server: `ollama pull {model}`), or choose --model from ollama_models.")
        except (OSError, ValueError, HTTPException) as exc:
            data["ollama_error"] = str(exc)
            check("ollama_server", False, str(exc),
                  "Start Ollama (for a local server: `ollama serve`) and verify --ollama-url and --model.")
    data["ready"] = all(item["ok"] for item in data["checks"])
    return data


def _setup_plan(mode="single-voice", base_url="http://localhost:11434", model="qwen3:14b"):
    """Build a read-only first-use report for the selected workflow."""
    profiles = {"mlx": _doctor("mlx", base_url, model)}
    if mode == "multi-voice":
        profiles["ollama"] = _doctor("ollama", base_url, model)
    ready = all(report["ready"] for report in profiles.values())
    next_steps = []
    mlx_failures = {check["name"]: check for check in profiles["mlx"]["checks"] if not check["ok"]}
    if "mlx_platform" in mlx_failures:
        next_steps.append(mlx_failures["mlx_platform"]["hint"])
    elif "mlx_audio" in mlx_failures:
        next_steps.append("From the raradio source checkout run `sh setup.sh mlx`.")
    next_steps.extend(
        check["hint"] for name, check in mlx_failures.items()
        if name not in {"mlx_platform", "mlx_audio"} and check.get("hint")
    )
    if mode == "multi-voice" and not profiles["ollama"]["ready"]:
        next_steps.extend(
            check["hint"] for check in profiles["ollama"]["checks"]
            if not check["ok"] and check.get("hint")
        )
    if ready:
        next_steps.append(
            "Dependencies are ready; follow the installation guide to create a cast and generate a short sample."
        )
    return {
        "version": __version__,
        "mode": mode,
        "ready": ready,
        "requires_ollama": mode == "multi-voice",
        "scope": "Read-only dependency preflight; this command does not install dependencies or download models.",
        "profiles": profiles,
        "next_steps": next_steps,
        "model_note": "The selected TTS model downloads on first speech generation and is cached for later runs.",
    }


def _print_setup_plan(plan):
    title = "Single voice" if plan["mode"] == "single-voice" else "Multiple voices"
    print(f"raradio setup — {title}")
    print(f"Speech dependencies: {'ready' if plan['profiles']['mlx']['ready'] else 'not ready'}")
    if plan["requires_ollama"]:
        print(f"Ollama: {'ready' if plan['profiles']['ollama']['ready'] else 'not ready'}")
    else:
        print("Ollama: not required")
    for report in plan["profiles"].values():
        for check in report["checks"]:
            if not check["ok"] and check.get("hint"):
                print(f"- {check['name']}: {check['hint']}")
    print("\nNext steps:")
    for step in plan["next_steps"]:
        print(f"- {step}")
    print(f"\nScope: {plan['scope']}")
    print(f"Model: {plan['model_note']}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="raradio", description="Local audiobooks: confirm the cast, generate speech, and review exceptions.")
    parser.add_argument("--version", action="version", version=f"raradio {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    sub = commands.add_parser("agent-guide", help="Print the bundled Agent Skill for using raradio without an analysis service")
    sub.add_argument("--format", choices=("markdown", "json"), default="markdown")
    sub = commands.add_parser("doctor", help="Check selected prerequisites without loading models; defaults to offline core checks")
    sub.add_argument("--profile", choices=("core", "mlx", "ollama"), default="core")
    sub.add_argument("--ollama-url", default="http://localhost:11434")
    sub.add_argument("--model", default="qwen3:14b")
    sub = commands.add_parser("setup", help="Check and explain first-use requirements without installing or downloading")
    sub.add_argument("--mode", choices=("single-voice", "multi-voice"), default="single-voice")
    sub.add_argument("--format", choices=("text", "json"), default="text")
    sub.add_argument("--ollama-url", default="http://localhost:11434")
    sub.add_argument("--model", default="qwen3:14b")
    for command in ("init", "build"):
        sub = commands.add_parser(command, help="Import source text" if command == "init" else "Import, analyze, generate, and optionally export; safe to resume")
        sub.add_argument("source", type=Path)
        sub.add_argument("--work", type=Path, required=True)
        sub.add_argument("--max-chars", type=_positive_int, help="Segment limit (new projects: 240; resume: saved value)")
        sub.add_argument("--encoding", help="Source encoding, e.g. cp932; default: UTF-8 or UTF-16/UTF-32 BOM")
        sub.add_argument("--chapters", choices=("auto", "none"), help="Detect conventional headings or keep one chapter")
        if command == "build":
            _analysis_options(sub)
            sub.add_argument("--cast", type=Path)
            sub.add_argument("--output", type=Path)
            sub.add_argument("--limit", type=_positive_int)
            sub.add_argument("--max-attempts", type=_positive_int, default=3)
    sub = commands.add_parser("analyze", help="Annotate speakers and emotions while preserving manual corrections")
    sub.add_argument("work", type=Path)
    _analysis_options(sub)
    sub = commands.add_parser("cast", help="Show the cast or import confirmed characters and voices")
    sub.add_argument("work", type=Path)
    sub.add_argument("--file", type=Path)
    for command in ("status", "segments", "review"):
        sub = commands.add_parser(command)
        sub.add_argument("work", type=Path)
    sub = commands.add_parser("structure", help="Export source spans, or apply reviewed chapter/boundary edits without rewriting text")
    sub.add_argument("work", type=Path)
    sub.add_argument("--file", type=Path)
    sub = commands.add_parser("resolve", help="Confirm a segment's speaker or correct its emotion")
    sub.add_argument("work", type=Path)
    sub.add_argument("segment")
    sub.add_argument("--speaker", required=True)
    sub.add_argument("--emotion")
    for command in ("retry", "accept-audio"):
        sub = commands.add_parser(command, help="Regenerate one segment" if command == "retry" else "Accept the current audio's quality warnings after listening")
        sub.add_argument("work", type=Path)
        sub.add_argument("segment")
    sub = commands.add_parser("run", help="Generate ready segments, reuse valid audio, and bound retries")
    sub.add_argument("work", type=Path)
    sub.add_argument("--limit", type=_positive_int)
    sub.add_argument("--max-attempts", type=_positive_int, default=3)
    sub = commands.add_parser("export", help="Export chapter WAVs, subtitles, and a manifest when all segments are done")
    sub.add_argument("work", type=Path)
    sub.add_argument("--output", type=Path, required=True)
    sub.add_argument("--pause-ms", type=_nonnegative_int, default=180)
    args = parser.parse_args(argv)
    try:
        if args.command == "agent-guide":
            guide = files("raradio").joinpath("skills/raradio-audiobook/SKILL.md").read_text(encoding="utf-8")
            if args.format == "json":
                _emit({"raradio_version": __version__, "skill_name": "raradio-audiobook", "skill_markdown": guide})
            else:
                print(guide, end="")
            return 0
        if args.command == "doctor":
            result = _doctor(args.profile, args.ollama_url, args.model)
            _emit(result)
            return 0 if result["ready"] else 1
        if args.command == "setup":
            result = _setup_plan(args.mode, args.ollama_url, args.model)
            _emit(result) if args.format == "json" else _print_setup_plan(result)
            return 0 if result["ready"] else 1
        if args.command == "init":
            _emit(BookProject.create(args.source, args.work, args.max_chars or 240,
                                     encoding=args.encoding, chapter_mode=args.chapters or "auto").status())
            return 0
        if args.command == "build":
            if args.work.exists():
                project = BookProject(args.work)
                for requested, key, fallback, option in (
                    (args.max_chars, "max_chars", 240, "--max-chars"),
                    (args.chapters, "chapter_mode", "auto", "--chapters"),
                ):
                    if requested is not None and requested != project.metadata.get(key, fallback):
                        raise ValueError(f"{option} differs from the saved project; use a new --work or edit structure explicitly")
                text = read_source(args.source, args.encoding or project.metadata.get("encoding"))
                with (project.root / "source.txt").open(encoding="utf-8", newline="") as stream:
                    saved_source = stream.read()
                if text != saved_source:
                    raise ValueError("This work directory belongs to different source text; use a new --work directory")
            else:
                project = BookProject.create(args.source, args.work, args.max_chars or 240,
                                             encoding=args.encoding, chapter_mode=args.chapters or "auto")
            if args.cast:
                _configure(project, args.cast)
            _analyze(project, args)
            result = _run(project, args)
            if args.output and result["remaining"] == 0:
                result["exports"] = [str(p) for p in project.export(args.output)]
            _emit(result)
            return 2 if result["remaining"] else 0
        project = BookProject(args.work)
        if args.command == "analyze":
            _emit(_analyze(project, args))
        elif args.command == "cast":
            if args.file:
                _configure(project, args.file)
            _emit(project.casting())
        elif args.command in ("status", "segments", "review"):
            _emit(getattr(project, args.command)())
        elif args.command == "structure":
            if args.file:
                project.restructure(json.loads(args.file.read_text(encoding="utf-8")))
            _emit(project.structure())
        elif args.command == "resolve":
            project.resolve(args.segment, args.speaker, args.emotion)
            _emit(project.status())
        elif args.command == "retry":
            project.retry(args.segment)
            _emit(project.status())
        elif args.command == "accept-audio":
            project.accept_audio(args.segment)
            _emit(project.status())
        elif args.command == "run":
            result = _run(project, args)
            _emit(result)
            return 2 if result["remaining"] else 0
        elif args.command == "export":
            _emit({"exports": [str(p) for p in project.export(args.output, args.pause_ms)]})
        return 0
    except (ValueError, OSError, RuntimeError, TypeError, sqlite3.Error) as exc:
        print(f"raradio: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Progress is saved; run the same command to resume.", file=sys.stderr)
        return 130
