"""Real import, review and repair workflows for manuscripts without reliable markup."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from raradio.analysis import RulesAnalyzer, SingleVoiceAnalyzer
from raradio.models import AnalysisResult
from raradio.project import BookProject
from tests.test_project import WaveBackend, cast


class TextWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "book.txt"
        self.work = self.base / "book"

    def create(self, text, **options):
        self.source.write_text(text, encoding="utf-8")
        project = BookProject.create(self.source, self.work, **options)
        project.configure(cast())
        return project

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "raradio", *map(str, args)],
                              capture_output=True, text=True)

    def test_llm_can_correct_unquoted_speech_without_rewriting_the_source(self):
        class SemanticAnalyzer:
            def analyze(self, segments, characters):
                return AnalysisResult([replace(s, kind="dialogue", speaker_id="alice", confidence=0.95)
                                       for s in segments], list(characters))

        project = self.create("小雨：明天见。")
        before = project.segments()[0]
        project.analyze(SemanticAnalyzer())
        backend = WaveBackend()
        project.run(backends={"tone": backend})
        self.assertEqual(backend.calls, [("小雨：明天见。", "alice")])
        after = project.segments()[0]
        self.assertEqual(after["kind"], "dialogue")
        self.assertEqual([(before[k], after[k]) for k in ("id", "text", "start", "end")],
                         [(before[k], before[k]) for k in ("id", "text", "start", "end")])

    def test_malformed_quote_waits_for_review_even_with_a_confident_analyzer(self):
        project = self.create("「おはよう。\n第二章 再会\n雨が降る。")
        self.assertTrue(project.review())
        project.analyze(SingleVoiceAnalyzer())
        backend = WaveBackend()
        project.run(backends={"tone": backend})
        review = project.review()
        self.assertEqual(len(review), 1)
        self.assertIn("parse:", review[0]["issue"])
        self.assertTrue(review[0]["parse_issues"])
        self.assertNotIn("「おはよう。", [text for text, _ in backend.calls])
        project.resolve(review[0]["id"], "narrator")
        project.run(backends={"tone": backend})
        self.assertEqual(project.status()["remaining"], 0)

    def test_structure_repair_splits_mixed_speakers_and_reuses_unaffected_audio(self):
        project = self.create("太郎：行こう。花子：待って。\n雨が降る。")
        project.analyze(RulesAnalyzer())
        project.run(backends={"tone": WaveBackend()})
        tail = project.segments()[-1]
        document = project.structure()
        first = document["segments"][0]
        cut = first["text"].index("花子")
        document["segments"][:1] = [
            dict(first, end=cut, text=first["text"][:cut], kind="dialogue"),
            dict(first, start=cut, text=first["text"][cut:], kind="dialogue"),
        ]
        project.restructure(document)
        restored = BookProject(self.work)
        self.assertEqual(restored.segments()[-1]["audio_sha"], tail["audio_sha"])
        self.assertEqual(restored.segments()[-1]["status"], "DONE")
        restored.analyze(RulesAnalyzer())
        for segment in restored.review():
            restored.resolve(segment["id"], "alice")
        backend = WaveBackend()
        restored.run(backends={"tone": backend})
        self.assertEqual(backend.calls, [("太郎：行こう。", "alice"), ("花子：待って。", "alice")])
        restored.export(self.base / "export", backends={"tone": backend})
        self.assertEqual((self.work / "source.txt").read_text(), "太郎：行こう。花子：待って。\n雨が降る。")

    def test_invalid_or_stale_structure_never_changes_existing_work(self):
        project = self.create("朝。\n夜。")
        original = project.structure()
        for change in ("text", "gap", "overlap", "source", "revision", "boolean_offset"):
            with self.subTest(change=change):
                bad = deepcopy(original)
                if change == "text":
                    bad["segments"][0]["text"] = "改写。"
                elif change == "gap":
                    bad["segments"].pop(0)
                elif change == "overlap":
                    bad["segments"].append(bad["segments"][0])
                elif change == "boolean_offset":
                    bad["segments"][0]["start"] = False
                else:
                    bad["source_sha256" if change == "source" else "revision"] = "wrong"
                before = project.segments()
                with self.assertRaises(ValueError):
                    project.restructure(bad)
                self.assertEqual(project.segments(), before)

    def test_explicit_encoding_and_chapter_mode_survive_build_resume(self):
        self.source.write_bytes("第一章を読み終えた。\n第二話 再会\nこんにちは。".encode("cp932"))
        config = self.base / "cast.json"
        config.write_text(json.dumps(cast()))
        args = ("build", self.source, "--work", self.work, "--encoding", "cp932",
                "--chapters", "none", "--analyzer", "single-voice", "--cast", config)
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        project = BookProject(self.work)
        self.assertEqual({s["chapter_title"] for s in project.segments()}, {"Main text"})
        hashes = [s["audio_sha"] for s in project.segments()]
        result = self.cli("build", self.source, "--work", self.work, "--analyzer", "single-voice")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([s["audio_sha"] for s in project.segments()], hashes)
        result = self.cli(*args, "--max-chars", "12")
        self.assertEqual(result.returncode, 1)
        self.assertIn("max-chars", result.stderr)

    def test_structure_cli_round_trip_can_assign_chapters_without_markers(self):
        project = self.create("朝。\n夜。")
        result = self.cli("structure", self.work)
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        document["segments"][1].update(chapter=2, chapter_title="夜の章")
        path = self.base / "structure.json"
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        result = self.cli("structure", self.work, "--file", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(project.segments()[1]["chapter_title"], "夜の章")

    def test_new_voice_configuration_does_not_force_japanese_text_into_chinese(self):
        class LanguageBackend(WaveBackend):
            def synthesize(self, text, voice, emotion, output):
                self.language = voice.language
                super().synthesize(text, voice, emotion, output)

        project = self.create("こんにちは。")
        project.analyze(SingleVoiceAnalyzer())
        backend = LanguageBackend()
        project.run(backends={"tone": backend})
        self.assertEqual(backend.language, "auto")
        config = cast()
        config["voices"]["narrator"]["language"] = "Japanese"
        project.configure(config)
        project.run(backends={"tone": backend})
        self.assertEqual(backend.language, "Japanese")

    def test_reanalyze_switches_modes_but_keeps_human_attribution(self):
        project = self.create("「行こう。」\n「待って。」")
        project.analyze(RulesAnalyzer())
        project.resolve(project.review()[0]["id"], "alice")
        result = self.cli("analyze", self.work, "--analyzer", "single-voice", "--reanalyze")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([s["speaker_id"] for s in project.segments()], ["alice", "narrator"])
        self.assertEqual(project.review(), [])

    def test_saved_confidence_threshold_controls_review(self):
        class UncertainAnalyzer:
            def analyze(self, segments, characters):
                return AnalysisResult([replace(s, speaker_id="narrator", confidence=0.85)
                                       for s in segments], list(characters))

        project = self.create("朝だった。")
        path = self.work / "project.json"
        metadata = json.loads(path.read_text())
        metadata["confidence_threshold"] = 0.9
        path.write_text(json.dumps(metadata))
        project = BookProject(self.work)
        project.analyze(UncertainAnalyzer())
        self.assertEqual(project.status()["counts"], {"NEEDS_REVIEW": 1})

    def test_legacy_projects_keep_their_original_implicit_voice_language(self):
        project = self.create("朝だった。")
        metadata_path = self.work / "project.json"
        metadata = json.loads(metadata_path.read_text())
        metadata.pop("default_language", None)
        metadata_path.write_text(json.dumps(metadata))
        legacy_cast = cast()
        (self.work / "cast.json").write_text(json.dumps(legacy_cast))
        project = BookProject(self.work)
        project.configure(legacy_cast)
        self.assertEqual(project.casting()["voices"]["narrator"]["language"], "Chinese")

    def test_failed_reanalysis_keeps_old_audio_blocked_until_analysis_succeeds(self):
        class FailedAnalyzer:
            def analyze(self, segments, characters):
                raise ValueError("invalid model annotation")

        project = self.create("朝だった。")
        project.analyze(RulesAnalyzer())
        project.run(backends={"tone": WaveBackend()})
        project.analyze(FailedAnalyzer(), reanalyze=True)
        backend = WaveBackend()
        project.run(backends={"tone": backend})
        self.assertEqual(project.status()["counts"], {"NEEDS_REVIEW": 1})
        self.assertIn("analysis:", project.review()[0]["issue"])
        with self.assertRaises(ValueError):
            project.export(self.base / "export", backends={"tone": backend})
        project.analyze(RulesAnalyzer())
        project.run(backends={"tone": backend})
        self.assertEqual(project.status()["remaining"], 0)

    def test_invalid_aliases_cannot_replace_a_working_cast(self):
        project = self.create("朝だった。")
        before = project.casting()
        for aliases in ([{}], [1], [" "], [False]):
            config = cast()
            config["characters"]["alice"]["aliases"] = aliases
            with self.subTest(aliases=aliases), self.assertRaises(ValueError):
                project.configure(config)
            self.assertEqual(project.casting(), before)

    def test_utf32_bom_is_not_mistaken_for_utf16(self):
        from raradio.project import read_source

        self.source.write_bytes("夜が明けた。".encode("utf-32"))
        self.assertEqual(read_source(self.source), "夜が明けた。")

    def test_bad_analyzer_confidence_is_reviewed_without_crashing(self):
        class BadAnalyzer:
            def analyze(self, segments, characters):
                return AnalysisResult([replace(s, speaker_id="narrator", confidence=10 ** 400)
                                       for s in segments], list(characters))

        project = self.create("朝だった。")
        project.analyze(BadAnalyzer())
        self.assertEqual(project.status()["counts"], {"NEEDS_REVIEW": 1})

    def test_invalid_project_threshold_is_reported_without_overflow(self):
        self.create("朝だった。")
        path = self.work / "project.json"
        metadata = json.loads(path.read_text())
        for value in (True, 10 ** 400, -0.1, "0.8"):
            metadata["confidence_threshold"] = value
            path.write_text(json.dumps(metadata))
            with self.subTest(value=value), self.assertRaises(ValueError):
                BookProject(self.work)

    def test_changing_a_chapter_title_does_not_erase_unresolved_parse_issues(self):
        project = self.create("「おはよう。")
        document = project.structure()
        document["segments"][0]["chapter_title"] = "朝"
        project.restructure(document)
        project.analyze(SingleVoiceAnalyzer())
        self.assertEqual(project.status()["counts"], {"NEEDS_REVIEW": 1})
        self.assertIn("parse:", project.review()[0]["issue"])

    def test_interrupted_reanalysis_cannot_export_old_completed_audio(self):
        class InterruptedAnalyzer:
            def analyze(self, segments, characters):
                raise KeyboardInterrupt()

        project = self.create("朝だった。\n第二章 夜\n夜だった。")
        project.analyze(RulesAnalyzer())
        project.run(backends={"tone": WaveBackend()})
        with self.assertRaises(KeyboardInterrupt):
            project.analyze(InterruptedAnalyzer(), reanalyze=True)
        project = BookProject(self.work)
        self.assertEqual(project.status()["counts"], {"NEEDS_REVIEW": 3})
        with self.assertRaises(ValueError):
            project.export(self.base / "export", backends={"tone": WaveBackend()})
        project.analyze(RulesAnalyzer())
        backend = WaveBackend()
        project.run(backends={"tone": backend})
        self.assertEqual(backend.calls, [])
        self.assertEqual(project.status()["remaining"], 0)

    def test_chapter_edits_preserve_human_attributions_and_audio(self):
        project = self.create("「行こう。」\n「待って。」")
        project.analyze(RulesAnalyzer())
        for item in project.review():
            project.resolve(item["id"], "alice")
        project.run(backends={"tone": WaveBackend()})
        before = project.segments()
        document = project.structure()
        document["segments"][1].update(chapter=2, chapter_title="夜")
        project.restructure(document)
        after = project.segments()
        self.assertEqual(after[1]["chapter"], 2)
        for original, updated in zip(before, after):
            for key in ("speaker_id", "reason", "audio_sha", "status"):
                self.assertEqual(original[key], updated[key])
        backend = WaveBackend()
        project.analyze(SingleVoiceAnalyzer(), reanalyze=True)
        project.run(backends={"tone": backend})
        self.assertEqual(backend.calls, [])
        self.assertEqual([s["speaker_id"] for s in project.segments()], ["alice", "alice"])


if __name__ == "__main__":
    unittest.main()
