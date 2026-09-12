"""Run the distributed examples; substitute only MLX loading and inference."""

from contextlib import contextmanager
from functools import partial
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from raradio.analysis import RulesAnalyzer, SingleVoiceAnalyzer
from raradio.project import BookProject
from tests.test_audio import write_wav
from tests.test_backends import generation_result


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


@contextmanager
def model_runtime():
    """Keep MlxBackend validation, routing, PCM writing and project QA real."""
    requests = []
    model_types = {
        "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit": "custom_voice",
        "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit": "base",
    }

    def generate(route, **request):
        requests.append((route, request))
        return iter([generation_result([0.0, 0.25, -0.25] * 8000)])

    def load_model(path):
        # Independent model metadata makes swapped Base/CustomVoice IDs fail.
        return SimpleNamespace(
            model_type="qwen3_tts", sample_rate=24000,
            config=SimpleNamespace(tts_model_type=model_types[path]),
            get_supported_speakers=lambda: ["serena", "vivian", "ryan"],
            get_supported_languages=lambda: ["auto", "chinese", "english"],
            speech_tokenizer=SimpleNamespace(has_encoder=True),
            speaker_encoder=object(),
            generate=partial(generate, "base"),
            generate_custom_voice=partial(generate, "custom_voice"),
        )

    modules = {
        "mlx": SimpleNamespace(),
        "mlx.core": SimpleNamespace(random=SimpleNamespace(seed=lambda seed: None)),
        "mlx_audio": SimpleNamespace(),
        "mlx_audio.tts": SimpleNamespace(),
        "mlx_audio.tts.utils": SimpleNamespace(load_model=load_model),
    }
    with patch.dict(sys.modules, modules):
        yield requests


class ExampleTemplateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def assert_export(self, project, destination, chapters=1):
        segments = project.segments()
        self.assertGreater(len(segments), 0)
        self.assertEqual(project.status()["counts"], {"DONE": len(segments)}, segments)
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["chapters"]), chapters)
        exported = []
        for chapter in manifest["chapters"]:
            exported.extend(chapter["segments"])
            self.assertTrue((destination / chapter["subtitles"]).read_text(encoding="utf-8"))
            with wave.open(str(destination / chapter["audio"]), "rb") as audio:
                self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()),
                                 (1, 2, 24000))
                self.assertGreater(audio.getnframes(), 0)
        self.assertEqual([item["id"] for item in exported], [item["id"] for item in segments])
        self.assertTrue(all(item["qa"]["issues"] == [] for item in exported))
        self.assertEqual((destination / "playlist.m3u").read_text(encoding="utf-8").splitlines()[1:],
                         [chapter["audio"] for chapter in manifest["chapters"]])
        source = (project.root / "source.txt").read_text(encoding="utf-8")
        self.assertEqual("".join(source.split()), "".join("".join(s["text"].split()) for s in segments))
        return segments

    def assert_resumes(self, project):
        # Content and nanosecond mtimes expose accidental successful regeneration.
        original = {p.name: (p.stat().st_mtime_ns, p.read_bytes())
                    for p in (project.root / "audio").glob("*.wav")}
        restored = BookProject(project.root)
        restored.run()
        self.assertEqual({p.name: (p.stat().st_mtime_ns, p.read_bytes())
                          for p in (project.root / "audio").glob("*.wav")}, original)
        self.assertEqual(restored.status()["remaining"], 0)

    def configure_template(self, project, filename):
        folder = self.directory / (filename + "-config")
        folder.mkdir()
        target = folder / "cast.json"
        shutil.copyfile(EXAMPLES / filename, target)
        config = json.loads(target.read_text(encoding="utf-8"))
        has_reference = any(voice.get("reference_audio") for voice in config["voices"].values())
        if has_reference:
            # Do not derive the path from the template: a wrong relative path must fail.
            write_wav(folder / "reference.wav", rate=24000)
        for voice in config["voices"].values():
            if voice.get("reference_text"):
                voice["reference_text"] = "这是参考录音实际说出的文字。"
        target.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        project.configure(json.loads(target.read_text(encoding="utf-8")), base_dir=target.parent)
        # Imported references must remain usable after the original config is gone.
        shutil.rmtree(folder)

    def test_public_diagnostic_inputs_export_and_resume_through_cli(self):
        # Catches missing distributed inputs, quoted dialogue blocking single voice,
        # lost chapter boundaries and templates that no longer complete offline.
        for filename, analyzer, chapters in [
            ("demo.txt", "rules", 1), ("story.txt", "single-voice", 1),
            ("clone.txt", "single-voice", 1), ("chapters.txt", "single-voice", 2),
            ("reference.txt", "single-voice", 1),
        ]:
            with self.subTest(filename=filename):
                project_path = self.directory / filename
                destination = self.directory / (filename + "-export")
                result = subprocess.run(
                    [sys.executable, "-S", "-m", "raradio", "build", str(EXAMPLES / filename),
                     "--work", str(project_path), "--analyzer", analyzer,
                     "--cast", str(EXAMPLES / "cast.tone.json"), "--output", str(destination)],
                    cwd=ROOT, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["remaining"], 0)
                project = BookProject(project_path)
                self.assert_export(project, destination, chapters)
                self.assert_resumes(project)

    def test_single_and_clone_templates_run_real_mlx_adapter_and_portable_references(self):
        # Catches model type mismatch, invalid clone controls, lost transcripts,
        # broken reference paths and successful inference that fails actual QA.
        cases = [("cast.single.json", "custom_voice", None),
                 ("cast.clone.xvector.json", "base", None),
                 ("cast.clone.icl.json", "base", "这是参考录音实际说出的文字。")]
        for filename, route, transcript in cases:
            with self.subTest(filename=filename), model_runtime() as requests:
                project = BookProject.create(EXAMPLES / "clone.txt", self.directory / filename)
                self.configure_template(project, filename)
                project.analyze(SingleVoiceAnalyzer())
                project.run(max_attempts=1)
                self.assertEqual(project.status()["remaining"], 0, project.segments())
                destination = self.directory / (filename + "-export")
                project.export(destination)
                segments = self.assert_export(project, destination)
                self.assertEqual({actual for actual, _ in requests}, {route})
                self.assertEqual([request["text"] for _, request in requests], [s["text"] for s in segments])
                for _, request in requests:
                    if route == "base":
                        self.assertEqual(request["ref_text"], transcript)
                        reference = Path(request["ref_audio"])
                        self.assertTrue(reference.is_relative_to(project.root / "voices"))
                        with wave.open(str(reference), "rb") as audio:
                            self.assertGreater(audio.getnframes(), 0)
                    else:
                        self.assertEqual(request["speaker"], "Serena")
                with wave.open(str(project.root / segments[0]["audio_path"]), "rb") as audio:
                    self.assertEqual(struct.unpack("<hhh", audio.readframes(3)), (0, 8192, -8192))
                self.assert_resumes(project)

    def test_multivoice_templates_preserve_the_complete_reviewed_cast(self):
        # All story characters must resolve, use their own voice and survive export.
        speakers = {"“我们回家吧。”": "xiaoyu", "“好，明天再来。”": "linzhou"}
        presets = {"narrator": "Serena", "xiaoyu": "Vivian", "linzhou": "Ryan"}
        for filename in ["cast.tone.multi.json", "cast.mlx.json", "cast.mixed.json"]:
            with self.subTest(filename=filename), model_runtime() as requests:
                project = BookProject.create(EXAMPLES / "story.txt", self.directory / filename)
                self.configure_template(project, filename)
                project.analyze(RulesAnalyzer())
                for segment in project.review():
                    project.resolve(segment["id"], speakers[segment["text"]])
                project.run(max_attempts=1)
                self.assertEqual(project.status()["remaining"], 0, project.segments())
                destination = self.directory / (filename + "-export")
                project.export(destination)
                segments = self.assert_export(project, destination)
                for segment in segments:
                    speaker = speakers.get(segment["text"], "narrator")
                    self.assertEqual(segment["speaker_id"], speaker)
                    self.assertEqual(segment["qa"]["generation"]["voice_id"], speaker)
                for route, request in requests:
                    if route == "custom_voice":
                        speaker = speakers.get(request["text"], "narrator")
                        self.assertEqual(request["speaker"], presets[speaker])
                if filename == "cast.mixed.json":
                    self.assertEqual([request["text"] for route, request in requests if route == "base"],
                                     ["“我们回家吧。”"])
                self.assert_resumes(project)


if __name__ == "__main__":
    unittest.main()
