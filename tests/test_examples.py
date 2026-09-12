import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "offline_workflow.py"


class OfflineWorkflowTests(unittest.TestCase):
    def test_public_example_keeps_attribution_and_only_regenerates_selected_audio(self):
        # Catches skipped manual resolution, full regeneration, and incomplete exports.
        source = ROOT / "examples" / "chapters.txt"
        cast = ROOT / "examples" / "cast.tone.multi.json"
        original_source, original_cast = source.read_bytes(), cast.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "demo with spaces"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--directory", str(directory)],
                cwd=temporary, capture_output=True, text=True, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(source.read_bytes(), original_source)
            self.assertEqual(cast.read_bytes(), original_cast)
            self.assertEqual((directory / "book" / "source.txt").read_bytes(), original_source)
            report = json.loads((directory / "verification.json").read_text(encoding="utf-8"))
            phases = report["snapshots"]
            self.assertEqual(report["limited_exit_code"], 2)
            self.assertEqual(sum(s["status"] == "DONE" for s in phases["limited"]), 2)
            self.assertTrue(any(s["status"] == "READY" for s in phases["limited"]))
            complete = {s["id"]: s for s in phases["complete"]}
            self.assertTrue(all(s["status"] == "DONE" for s in complete.values()))
            self.assertEqual(phases["complete"], phases["cached"])

            retry_pending = {s["id"]: s for s in phases["retry_pending"]}
            retried_ids = [key for key in complete if retry_pending[key]["status"] == "READY"]
            self.assertEqual(len(retried_ids), 1)
            retried_id = retried_ids[0]
            retried = {s["id"]: s for s in phases["retried"]}
            self.assertGreater(retried[retried_id]["mtime_ns"], complete[retried_id]["mtime_ns"])
            self.assertEqual(retried[retried_id]["status"], "DONE")
            for key in complete:
                if key != retried_id:
                    self.assertEqual(complete[key], retry_pending[key])
                    self.assertEqual(complete[key], retried[key])

            voice_pending = {s["id"]: s for s in phases["voice_pending"]}
            final = {s["id"]: s for s in phases["voice_changed"]}
            changed_ids = [key for key in final if voice_pending[key]["status"] == "READY"]
            self.assertEqual(len(changed_ids), 2)
            for key, segment in final.items():
                self.assertEqual(segment["status"], "DONE")
                self.assertEqual(segment["accepted"], 0)
                if segment["speaker_id"] == "xiaoyu":
                    self.assertIn(key, changed_ids)
                    self.assertNotEqual(segment["audio_sha"], retried[key]["audio_sha"])
                    self.assertNotEqual(segment["audio_path"], retried[key]["audio_path"])
                else:
                    self.assertEqual(retried[key], voice_pending[key])
                    self.assertEqual(retried[key], segment)

            segments = list(final.values())
            quoted = [(s["text"], s["speaker_id"]) for s in segments if s["kind"] == "dialogue"]
            self.assertEqual(quoted, [
                ("“我们去河边吧。”", "xiaoyu"),
                ("“好，带上雨伞。”", "linzhou"),
                ("“雨雨”", "narrator"),
                ("“明天还来吗？”", "xiaoyu"),
                ("“当然，我会在这里等你。”", "linzhou"),
            ])
            self.assertTrue(all(s["speaker_id"] == "narrator" for s in segments if s["kind"] == "narration"))
            text = original_source.decode("utf-8")
            self.assertEqual("".join(s["text"] for s in segments).replace("\n", "").replace(" ", ""),
                             "".join(text.split()))
            for segment in segments:
                self.assertEqual(text[segment["start"]:segment["end"]], segment["text"])
                audio = directory / "book" / segment["audio_path"]
                self.assertEqual(hashlib.sha256(audio.read_bytes()).hexdigest(), segment["audio_sha"])

            exported = directory / "export"
            manifest = json.loads((exported / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([c["title"] for c in manifest["chapters"]],
                             ["第一章 雨后的约定", "第二章 第二天"])
            self.assertEqual(len(list(exported.glob("*.wav"))), 2)
            self.assertEqual(len(list(exported.glob("*.srt"))), 2)
            self.assertEqual((exported / "playlist.m3u").read_text(encoding="utf-8").splitlines(),
                             ["#EXTM3U", "chapter-0001.wav", "chapter-0002.wav"])
            exported_ids = []
            for chapter in manifest["chapters"]:
                with wave.open(str(exported / chapter["audio"]), "rb") as audio:
                    self.assertEqual(audio.getnframes(), chapter["frames"])
                    self.assertGreater(audio.getnframes(), 0)
                    self.assertEqual(audio.getframerate(), 24000)
                    self.assertEqual(len(audio.readframes(audio.getnframes())), chapter["frames"] * 2)
                subtitles = (exported / chapter["subtitles"]).read_text(encoding="utf-8")
                self.assertEqual(subtitles.count(" --> "), len(chapter["segments"]))
                for segment in chapter["segments"]:
                    exported_ids.append(segment["id"])
                    self.assertIn(segment["text"], subtitles)
                    self.assertEqual(segment["sha256"], final[segment["id"]]["audio_sha"])
            self.assertEqual(exported_ids, list(final))

    def test_existing_directory_is_refused_without_changing_its_files(self):
        # Catches overwriting a previous demo or silently placing another book inside it.
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "existing demo"
            directory.mkdir()
            sentinel = directory / "keep.txt"
            sentinel.write_bytes(b"previous work\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--directory", str(directory)],
                cwd=temporary, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(sentinel.read_bytes(), b"previous work\n")
            self.assertEqual(list(directory.iterdir()), [sentinel])
            self.assertIn(str(directory), result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
