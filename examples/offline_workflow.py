#!/usr/bin/env python3
"""Run the public two-chapter example through the real CLI, without a model.

Attribution is known in advance for this original sample. The script stands in
for a human reviewer; it does not identify speakers in arbitrary novels.
"""

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "chapters.txt"
CAST = ROOT / "examples" / "cast.tone.multi.json"

# Original sample's answer key, not an attribution algorithm. Resolve uses IDs
# returned by `raradio segments`, so no IDs or source offsets are invented here.
KNOWN_QUOTES = {
    "“我们去河边吧。”": "xiaoyu",
    "“好，带上雨伞。”": "linzhou",
    "“雨雨”": "narrator",
    "“明天还来吗？”": "xiaoyu",
    "“当然，我会在这里等你。”": "linzhou",
}


def execute(explanation, command, expected=0):
    print(f"\n{explanation}", flush=True)
    print(f"$ (cd {shlex.quote(str(ROOT))} && {shlex.join(command)})", flush=True)
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr, flush=True)
    if result.returncode != expected:
        if result.stdout:
            print(result.stdout.rstrip(), flush=True)
        raise RuntimeError(f"Command exited with {result.returncode}, expected {expected}; see the command and error above")
    return result


def cli(explanation, *arguments, expected=0):
    command = [sys.executable, "-m", "raradio", *map(str, arguments)]
    result = execute(explanation, command, expected)
    data = json.loads(result.stdout)
    if isinstance(data, dict) and "counts" in data:
        print(f"Exit code {result.returncode}; status {data['counts']}; remaining {data['remaining']}")
    elif isinstance(data, list):
        print(f"Exit code {result.returncode}; {len(data)} segments")
    else:
        print(result.stdout.rstrip())
    return data


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def snapshot(book, explanation):
    segments = cli(explanation, "segments", book)
    for segment in segments:
        path = segment["audio_path"]
        segment["mtime_ns"] = (book / path).stat().st_mtime_ns if path else None
    return segments


def changed(before, after):
    previous = {segment["id"]: segment for segment in before}
    return {segment["id"] for segment in after if previous[segment["id"]] != segment}


def workflow(directory):
    book = directory / "book"
    output = directory / "export"
    report = {"snapshots": {}}
    stages = report["snapshots"]

    print(f"Result directory: {directory}")
    print("This example uses examples/chapters.txt and cast.tone.multi.json; no models or network access are required.")
    print("The tone backend generates diagnostic beeps, not speech.")
    print("Attribution comes from the known answers for this original sample; the script demonstrates manual review, not automatic speaker identification.")
    print("The four spoken lines belong to Xiaoyu, Linzhou, Xiaoyu, and Linzhou; the quoted alias is part of the narration.")

    cast = json.loads(CAST.read_text(encoding="utf-8"))
    require(all(voice.get("backend") == "tone" for voice in cast["voices"].values()),
            "This offline example only allows tone voices; restore the public cast.tone.multi.json template")

    cli("1. Import the public two-chapter source, preserving its text and actual segment IDs.", "init", SOURCE, "--work", book)
    cli("2. Use rules to identify narration; leave quoted passages for manual review.", "analyze", book, "--analyzer", "rules")
    review = cli("3. Inspect the review queue; the narrator voice is not yet confirmed either.", "review", book)
    for segment in review:
        print(f"  {segment['id']}  {segment['text']}  [{segment['issue']}]")

    cli("4. Demonstrate manual confirmation: import the complete narrator, Xiaoyu, and Linzhou cast, including aliases and three tone voices.",
        "cast", book, "--file", CAST)
    segments = cli("5. Read the actual segment IDs and match the known attribution for this original sample.", "segments", book)
    quotes = [segment for segment in segments if segment["kind"] == "dialogue"]
    require([segment["text"] for segment in quotes] == list(KNOWN_QUOTES),
            "Quoted passages in the public sample have changed; review their attribution and update the answer key")
    for segment in quotes:
        speaker = KNOWN_QUOTES[segment["text"]]
        cli(f"Demonstrate manual resolve: {segment['text']} -> {speaker}.",
            "resolve", book, segment["id"], "--speaker", speaker)
    require(cli("Check that the attribution review queue is empty.", "review", book) == [], "Some segments still need manual review")

    limited = cli("6. Generate two segments first; exit code 2 means work remains and can be resumed.",
                  "run", book, "--limit", "2", expected=2)
    report["limited_exit_code"] = 2
    require(limited["counts"].get("DONE") == 2 and limited["remaining"] > 0,
            "The limited run did not leave the expected pending segments")
    stages["limited"] = snapshot(book, "Record progress after the limited run.")
    cli("7. Resume and complete the remaining segments.", "run", book)
    stages["complete"] = snapshot(book, "Record audio paths, hashes, and modification times after the first complete run.")
    cli("8. Repeat the command and check that all completed segments reuse cached audio.", "run", book)
    stages["cached"] = snapshot(book, "Read the actual audio state after repeating the command.")
    require(stages["complete"] == stages["cached"], "Cache verification failed: repeating an unchanged run altered the audio")
    print("Verified: an unchanged run preserves all audio files and modification times.")

    retry_id = quotes[0]["id"]
    cli("9. Demonstrate regenerating only the first spoken line.", "retry", book, retry_id)
    stages["retry_pending"] = snapshot(book, "Check that only the selected segment returns to READY.")
    require(changed(stages["cached"], stages["retry_pending"]) == {retry_id},
            "Retrying one segment unexpectedly affected other segments")
    cli("Generate the selected segment and reuse cached audio for the rest.", "run", book)
    stages["retried"] = snapshot(book, "Inspect the audio files after regenerating one segment.")
    require(changed(stages["cached"], stages["retried"]) == {retry_id},
            "Single-segment regeneration failed: the selected audio was not rewritten, or other cached results changed")
    print("Verified: only the selected segment was regenerated; deterministic tone output may retain its hash, but its modification time changes.")

    modified_cast = directory / "cast.speed.json"
    edit = (
        "import json, pathlib, sys; "
        "data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')); "
        "data['voices']['xiaoyu']['speed'] = 1.25; "
        "pathlib.Path(sys.argv[2]).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')"
    )
    execute("10. Copy the complete cast and set the Xiaoyu tone speed to 1.25, preserving all characters and other voices.",
            [sys.executable, "-c", edit, str(CAST), str(modified_cast)])
    cli("Import the complete cast again to invalidate audio for the Xiaoyu voice.", "cast", book, "--file", modified_cast)
    stages["voice_pending"] = snapshot(book, "Check that only Xiaoyu segments are pending generation.")
    xiaoyu_ids = {segment["id"] for segment in stages["retried"] if segment["speaker_id"] == "xiaoyu"}
    require(changed(stages["retried"], stages["voice_pending"]) == xiaoyu_ids,
            "The voice configuration change affected segments other than Xiaoyu")
    cli("Generate only the Xiaoyu segments.", "run", book)
    stages["voice_changed"] = snapshot(book, "Record the final state after changing the voice.")
    require(changed(stages["retried"], stages["voice_changed"]) == xiaoyu_ids,
            "Partial regeneration after changing the Xiaoyu voice failed verification")
    require(all(segment["status"] == "DONE" and not segment["accepted"]
                for segment in stages["voice_changed"]), "Some segments are unfinished or have accepted audio quality warnings")
    require((book / "source.txt").read_bytes() == SOURCE.read_bytes(), "The source text in the project has changed")
    print("Verified: only the two Xiaoyu lines were regenerated; narrator and Linzhou audio was preserved.")

    cli("11. Export two chapter WAVs, SRTs, manifest.json, and playlist.m3u after completion.",
        "export", book, "--output", output)
    report_path = directory / "verification.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nDone. Project: {book}\nExport: {output}\nVerification report: {report_path}")
    print("All results are retained; each default run creates a new directory.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path,
                        help="New result directory (must not exist); defaults to a unique directory under work/ in the source root")
    args = parser.parse_args()
    directory = None
    try:
        if args.directory is not None:
            requested = args.directory.expanduser().absolute()
            try:
                requested.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                raise ValueError(f"Directory already exists and will not be overwritten: {requested}; choose a new directory") from None
            directory = requested.resolve()
        else:
            work = ROOT / "work"
            work.mkdir(exist_ok=True)
            directory = Path(tempfile.mkdtemp(prefix="offline-", dir=work))
        workflow(directory)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print(f"offline_workflow: {error}", file=sys.stderr)
        if directory is not None:
            print(f"Generated results are retained in: {directory}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"\nInterrupted; existing results are retained in: {directory}", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
