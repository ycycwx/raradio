import json
import math
import shutil
import sqlite3
import struct
import tempfile
import unittest
import wave
import threading
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from raradio.project import BookProject


class WaveBackend:
    version = "test-wave-v1"

    def __init__(self, failures=0, silent=False):
        self.calls = []
        self.failures = failures
        self.silent = silent

    def synthesize(self, text, voice, emotion, output):
        self.calls.append((text, voice.id))
        if len(self.calls) <= self.failures:
            raise RuntimeError("temporary inference failure")
        with wave.open(str(output), "wb") as wav:
            wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            wav.writeframes(b"".join(struct.pack("<h", 0 if self.silent else int(6000 * math.sin(i / 8))) for i in range(16000)))


def cast(backend="tone"):
    return {
        "characters": {
            "narrator": {"name": "旁白", "voice": "narrator", "confirmed": True},
            "alice": {"name": "小雨", "voice": "alice", "confirmed": True},
        },
        "voices": {
            "narrator": {"backend": backend},
            "alice": {"backend": backend},
        },
    }


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def create(self, text="窗外下着雨。\n灯还亮着。"):
        source = self.base / "book.txt"
        source.write_text(text, encoding="utf-8")
        return BookProject.create(source, self.base / "book")

    def ready(self, text="窗外下着雨。\n灯还亮着。"):
        from raradio.analysis import RulesAnalyzer
        project = self.create(text)
        project.analyze(RulesAnalyzer())
        project.configure(cast())
        return project

    def test_original_and_progress_survive_reopen_and_rerun(self):
        project = self.ready()
        backend = WaveBackend()
        project.run(backends={"tone": backend})
        first_calls = len(backend.calls)
        self.assertGreater(first_calls, 0)
        restored = BookProject(project.root)
        restored.run(backends={"tone": backend})
        self.assertEqual(len(backend.calls), first_calls)
        self.assertEqual(restored.status()["counts"], {"DONE": first_calls})
        self.assertEqual((project.root / "source.txt").read_text(), "窗外下着雨。\n灯还亮着。")

    def test_ambiguous_dialogue_waits_for_explicit_speaker_then_runs(self):
        project = self.ready("小雨说：\n“明天见。”")
        reviews = project.review()
        self.assertEqual(len(reviews), 1)
        self.assertIn("speaker", reviews[0]["issue"])
        backend = WaveBackend()
        project.run(backends={"tone": backend})
        self.assertFalse(any("明天见" in text for text, _ in backend.calls))
        project.resolve(reviews[0]["id"], speaker_id="alice")
        project.run(backends={"tone": backend})
        self.assertTrue(any("明天见" in text and voice == "alice" for text, voice in backend.calls))
        self.assertEqual(project.review(), [])

    def test_changing_one_voice_only_invalidates_that_speaker(self):
        project = self.ready("风停了。\n“明天见。”")
        project.resolve(project.review()[0]["id"], speaker_id="alice")
        backend = WaveBackend()
        project.run(backends={"tone": backend})
        backend.calls.clear()
        updated = cast()
        updated["voices"]["alice"]["seed"] = 12
        project.configure(updated)
        project.run(backends={"tone": backend})
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(backend.calls[0][1], "alice")

    def test_retries_are_bounded_and_failed_segments_need_explicit_reset(self):
        project = self.ready("窗外下着雨。")
        backend = WaveBackend(failures=100)
        project.run(backends={"tone": backend}, max_attempts=2)
        self.assertEqual(len(backend.calls), 2)
        self.assertEqual(project.segments()[0]["status"], "FAILED")
        project.run(backends={"tone": backend}, max_attempts=2)
        self.assertEqual(len(backend.calls), 2)
        project.retry(project.segments()[0]["id"])
        project.run(backends={"tone": WaveBackend()}, max_attempts=2)
        self.assertEqual(project.status()["counts"], {"DONE": 1})

    def test_suspicious_audio_blocks_export_until_review(self):
        project = self.ready("窗外下着雨。")
        project.run(backends={"tone": WaveBackend(silent=True)}, max_attempts=2)
        self.assertEqual(project.segments()[0]["status"], "NEEDS_REVIEW")
        self.assertIn("silence", project.review()[0]["issue"])
        with self.assertRaises(ValueError):
            project.export(self.base / "exports")
        project.retry(project.review()[0]["id"])
        project.run(backends={"tone": WaveBackend()})
        outputs = project.export(self.base / "exports", backends={"tone": WaveBackend()})
        self.assertTrue(outputs[0].is_file())

    def test_corrupt_cache_is_regenerated_and_project_can_move(self):
        project = self.ready("灯还亮着。")
        project.run(backends={"tone": WaveBackend()})
        audio = project.root / project.segments()[0]["audio_path"]
        audio.write_bytes(b"broken")
        relocated = self.base / "relocated"
        shutil.copytree(project.root, relocated)
        moved = BookProject(relocated)
        backend = WaveBackend()
        moved.run(backends={"tone": backend})
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(moved.status()["counts"], {"DONE": 1})

    def test_interrupted_generation_is_recovered(self):
        project = self.ready("灯还亮着。")
        with closing(sqlite3.connect(project.root / "state.sqlite3")) as db, db:
            db.execute("UPDATE segments SET status='GENERATING', attempts=1")
        project.run(backends={"tone": WaveBackend()})
        self.assertEqual(project.status()["counts"], {"DONE": 1})

    def test_init_refuses_overwriting_existing_project(self):
        project = self.create()
        with self.assertRaises(FileExistsError):
            BookProject.create(self.base / "book.txt", project.root)
        self.assertEqual((project.root / "source.txt").read_text(), "窗外下着雨。\n灯还亮着。")

    def test_invalid_cast_does_not_replace_working_configuration(self):
        project = self.ready()
        before = (project.root / "cast.json").read_bytes()
        bad = cast()
        bad["characters"]["narrator"]["voice"] = "missing"
        with self.assertRaises(ValueError):
            project.configure(bad)
        self.assertEqual((project.root / "cast.json").read_bytes(), before)

    def test_invalid_voice_types_preserve_cast_and_completed_audio(self):
        project = self.ready("灯还亮着。")
        project.run(backends={"tone": WaveBackend()})
        before_cast = (project.root / "cast.json").read_bytes()
        before_segments = project.segments()
        invalid = [("seed", "42"), ("seed", None), ("seed", True), ("seed", 1.5),
                   ("speed", True), ("temperature", "0.7"), ("temperature", True),
                   ("temperature", -1), ("model", 42), ("instruct", None), ("speaker", 42),
                   ("reference_audio", False), ("reference_text", 42),
                   ("clone_mode", None), ("emotion_mode", [])]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                bad = cast()
                bad["voices"]["narrator"][field] = value
                with self.assertRaises(ValueError):
                    project.configure(bad)
                self.assertEqual((project.root / "cast.json").read_bytes(), before_cast)
                self.assertEqual(project.segments(), before_segments)

    def test_reimport_reuses_valid_reference_without_rewriting_it(self):
        project = self.ready("灯还亮着。")
        original = self.base / "reference.wav"
        original.write_bytes(b"reference bytes")
        config = cast()
        config["voices"]["narrator"]["reference_audio"] = str(original)
        project.configure(config)
        project.run(backends={"tone": WaveBackend()})
        saved = project.root / project.casting()["voices"]["narrator"]["reference_audio"]
        before = (saved.read_bytes(), saved.stat().st_mtime_ns, project.segments())

        def interrupted_copy(source, destination):
            Path(destination).write_bytes(b"partial")
            raise OSError("copy interrupted")

        with patch("raradio.project.shutil.copyfile", interrupted_copy):
            try:
                project.configure(config)
            except OSError as exc:
                self.fail(f"Reimport rewrote a valid reference: {exc}")
        self.assertEqual((saved.read_bytes(), saved.stat().st_mtime_ns, project.segments()), before)

    def test_failed_reference_copy_does_not_publish_partial_media(self):
        project = self.ready()
        original = self.base / "reference.wav"
        original.write_bytes(b"reference bytes")
        config = cast()
        config["voices"]["narrator"]["reference_audio"] = str(original)
        before = (project.root / "cast.json").read_bytes()

        def interrupted_copy(source, destination):
            Path(destination).write_bytes(b"partial")
            raise KeyboardInterrupt

        with patch("raradio.project.shutil.copyfile", interrupted_copy), self.assertRaises(KeyboardInterrupt):
            project.configure(config)
        self.assertEqual((project.root / "cast.json").read_bytes(), before)
        self.assertEqual(list((project.root / "voices").iterdir()), [])

    def test_reference_changed_during_copy_cannot_publish_under_old_hash(self):
        project = self.ready()
        original = self.base / "reference.wav"
        original.write_bytes(b"original reference")
        config = cast()
        config["voices"]["narrator"]["reference_audio"] = str(original)
        before = (project.root / "cast.json").read_bytes()

        def changed_copy(source, destination):
            Path(destination).write_bytes(b"changed reference")

        with patch("raradio.project.shutil.copyfile", changed_copy), self.assertRaises(ValueError):
            project.configure(config)
        self.assertEqual((project.root / "cast.json").read_bytes(), before)
        self.assertEqual(list((project.root / "voices").iterdir()), [])

    def test_reanalysis_does_not_overwrite_human_speaker_correction(self):
        from raradio.analysis import RulesAnalyzer
        project = self.ready("“明天见。”")
        segment_id = project.review()[0]["id"]
        project.resolve(segment_id, speaker_id="alice")
        project.analyze(RulesAnalyzer())
        self.assertEqual(project.segments()[0]["speaker_id"], "alice")

    def test_repeated_text_does_not_overwrite_previous_valid_artifact(self):
        class VariableBackend(WaveBackend):
            def synthesize(self, text, voice, emotion, output):
                super().synthesize(text, voice, emotion, output)
                with wave.open(str(output), "rb") as audio:
                    params, frames = audio.getparams(), audio.readframes(audio.getnframes())
                with wave.open(str(output), "wb") as audio:
                    audio.setparams(params)
                    audio.writeframes(frames + frames * (len(self.calls) - 1))

        project = self.ready("灯还亮着。\n灯还亮着。")
        project.run(backends={"tone": VariableBackend()})
        self.assertEqual(project.status()["remaining"], 0)
        self.assertTrue(project.export(self.base / "export", backends={"tone": VariableBackend()})[0].exists())

    def test_new_aliases_are_carried_to_the_next_chapter(self):
        from raradio.analysis import RulesAnalyzer
        from raradio.models import AnalysisResult, Character

        class AliasAnalyzer:
            seen = []

            def analyze(self, segments, characters):
                self.seen.append(characters)
                annotated = RulesAnalyzer().analyze(segments, characters)
                return AnalysisResult(annotated.segments, [Character("alice", "小雨", ("雨雨",))])

        project = self.create("第一章\n灯还亮着。\n第二章\n雨停了。")
        project.configure(cast())
        analyzer = AliasAnalyzer()
        project.analyze(analyzer)
        self.assertIn("雨雨", next(c.aliases for c in analyzer.seen[1] if c.id == "alice"))
        self.assertTrue(project.casting()["characters"]["alice"]["confirmed"])

    def test_export_refuses_stale_backend_version(self):
        from unittest.mock import patch
        from raradio.backends import ToneBackend

        project = self.ready("灯还亮着。")
        project.run()
        with patch.object(ToneBackend, "version", "a-new-renderer"):
            with self.assertRaisesRegex(ValueError, "backend"):
                project.export(self.base / "export")

    def test_limited_run_invalidates_every_missing_cache_before_reporting_completion(self):
        project = self.ready("灯还亮着。\n雨已经停了。")
        project.run(backends={"tone": WaveBackend()})
        self.assertEqual(len(project.segments()), 2)
        for segment in project.segments():
            (project.root / segment["audio_path"]).unlink()
        backend = WaveBackend()
        result = project.run(backends={"tone": backend}, limit=1)
        self.assertEqual(result["remaining"], 1)
        self.assertEqual(result["counts"], {"DONE": 1, "READY": 1})
        self.assertEqual(len(backend.calls), 1)
        pending = project.segments()[1]
        self.assertEqual(pending["attempts"], 0)
        self.assertIsNone(pending["audio_path"])
        self.assertIsNone(pending["audio_sha"])
        self.assertEqual(pending["qa"], {})
        self.assertEqual(project.run(backends={"tone": backend}, limit=1)["remaining"], 0)
        self.assertEqual(len(backend.calls), 2)
        self.assertTrue(project.export(self.base / "export", backends={"tone": backend})[0].exists())

    def test_limited_backend_upgrade_invalidates_all_old_audio_before_generation(self):
        class NewBackend(WaveBackend):
            version = "new-backend-v2"

        project = self.ready("灯还亮着。\n雨已经停了。")
        project.run(backends={"tone": WaveBackend(silent=True)}, max_attempts=1)
        for segment in project.review():
            project.accept_audio(segment["id"])
        backend = NewBackend()
        result = project.run(backends={"tone": backend}, limit=1, max_attempts=1)
        self.assertEqual(result["remaining"], 1)
        self.assertEqual(len(backend.calls), 1)
        pending = project.segments()[1]
        self.assertEqual(pending["status"], "READY")
        self.assertEqual(pending["attempts"], 0)
        self.assertEqual(pending["accepted"], 0)
        self.assertEqual(pending["qa"], {})
        self.assertIsNone(pending["audio_path"])
        self.assertEqual(project.run(backends={"tone": backend}, limit=1, max_attempts=1)["remaining"], 0)
        self.assertEqual(len(backend.calls), 2)
        self.assertTrue(project.export(self.base / "export", backends={"tone": backend})[0].exists())

    def test_quality_retry_uses_a_new_recorded_seed(self):
        class SeedSensitiveBackend(WaveBackend):
            def synthesize(self, text, voice, emotion, output):
                self.silent = voice.seed == 0
                super().synthesize(text, voice, emotion, output)

        project = self.ready("灯还亮着。")
        project.run(backends={"tone": SeedSensitiveBackend()}, max_attempts=2)
        item = project.segments()[0]
        self.assertEqual(item["status"], "DONE")
        self.assertEqual(item["attempts"], 2)
        self.assertEqual(item["qa"]["generation"]["seed"], 1)

    def test_interrupting_the_last_attempt_does_not_consume_retry_budget(self):
        class InterruptedBackend(WaveBackend):
            def synthesize(self, text, voice, emotion, output):
                raise KeyboardInterrupt()

        project = self.ready("灯还亮着。")
        with self.assertRaises(KeyboardInterrupt):
            project.run(backends={"tone": InterruptedBackend()}, max_attempts=1)
        backend = WaveBackend()
        project.run(backends={"tone": backend}, max_attempts=1)
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(project.status()["counts"], {"DONE": 1})

    def test_temporary_character_unconfirmation_preserves_audio_review(self):
        project = self.ready("灯还亮着。")
        project.run(backends={"tone": WaveBackend(silent=True)}, max_attempts=1)
        unconfirmed = cast()
        unconfirmed["characters"]["narrator"]["confirmed"] = False
        project.configure(unconfirmed)
        project.configure(cast())
        self.assertIn("audio:", project.review()[0]["issue"])
        self.assertIn("silence", project.review()[0]["issue"])

    def test_copied_reference_survives_removing_original_and_moving_book(self):
        project = self.ready("灯还亮着。")
        original = self.base / "reference.wav"
        from raradio.models import VoiceProfile
        WaveBackend().synthesize("参考语音。", VoiceProfile("n"), "neutral", original)
        config = cast()
        config["voices"]["narrator"]["reference_audio"] = str(original)
        project.configure(config)
        saved = project.casting()["voices"]["narrator"]["reference_audio"]
        self.assertFalse(Path(saved).is_absolute())
        self.assertEqual((project.root / saved).read_bytes(), original.read_bytes())
        original.unlink()
        project.run(backends={"tone": WaveBackend()})
        moved = self.base / "moved-book"
        shutil.copytree(project.root, moved)
        backend = WaveBackend()
        BookProject(moved).run(backends={"tone": backend})
        self.assertEqual(backend.calls, [])

    def test_second_writer_cannot_modify_a_running_book(self):
        entered, finish = threading.Event(), threading.Event()

        class SlowBackend(WaveBackend):
            def synthesize(self, text, voice, emotion, output):
                entered.set()
                finish.wait(5)
                super().synthesize(text, voice, emotion, output)

        project = self.ready("灯还亮着。")
        worker = threading.Thread(target=project.run, kwargs={"backends": {"tone": SlowBackend()}})
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaisesRegex(RuntimeError, "another process"):
                BookProject(project.root).configure(cast())
        finally:
            finish.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(project.status()["counts"], {"DONE": 1})

    def test_failed_backend_upgrade_cannot_bless_old_audio_after_cast_review(self):
        class NewBackend(WaveBackend):
            version = "new-backend-v2"

        project = self.ready("灯还亮着。")
        project.run(backends={"tone": WaveBackend()})
        project.run(backends={"tone": NewBackend(failures=10)}, max_attempts=1)
        unconfirmed = cast()
        unconfirmed["characters"]["narrator"]["confirmed"] = False
        project.configure(unconfirmed)
        project.configure(cast())
        with self.assertRaises(ValueError):
            project.export(self.base / "export", backends={"tone": NewBackend()})


if __name__ == "__main__":
    unittest.main()
