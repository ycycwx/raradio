"""Real PCM fixtures exercise corruption and chapter publication boundaries."""

import math
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from raradio.audio import export_chapters, inspect_wav


def write_wav(path, *, duration=1.0, rate=8000, channels=1, samples=None, width=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    if samples is None:
        samples = [int(6000 * math.sin(2 * math.pi * 220 * n / rate))
                   for n in range(round(duration * rate)) for _ in range(channels)]
    with wave.open(str(path), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(width)
        target.setframerate(rate)
        target.writeframes(struct.pack("<" + "h" * len(samples), *samples)
                           if width == 2 else bytes(samples))
    return path


class InspectWavTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_reads_real_sample_duration_and_stereo_format(self):
        path = write_wav(self.root / "voice.wav", duration=1.25, channels=2)
        result = inspect_wav(path, "你好，这是一段语音。")
        self.assertEqual(result, {"duration": 1.25, "sample_rate": 8000,
                                  "channels": 2, "issues": []})

    def test_rejects_missing_corrupt_empty_non_pcm16_and_truncated_media(self):
        bad = self.root / "bad.wav"
        bad.write_bytes(b"not a wave")
        empty = write_wav(self.root / "empty.wav", samples=[])
        narrow = write_wav(self.root / "8bit.wav", samples=[128] * 8000, width=1)
        truncated = write_wav(self.root / "truncated.wav")
        truncated.write_bytes(truncated.read_bytes()[:-200])
        for path in (self.root / "missing.wav", bad, empty, narrow, truncated):
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                inspect_wav(path, "你好")

    def test_flags_silence_sparse_signal_and_clipping(self):
        for name, samples, expected in (
            ("quiet", [0] * 8000, "silence"),
            ("sparse", [4000] * 8 + [0] * 7992, "sparse_signal"),
            ("clip", [32767, -32768] * 4000, "clipping"),
        ):
            with self.subTest(name=name):
                result = inspect_wav(write_wav(self.root / (name + ".wav"), samples=samples), "你好")
                self.assertIn(expected, result["issues"])

    def test_flags_implausible_duration_for_multilingual_text(self):
        short = write_wav(self.root / "short.wav", duration=0.1)
        long = write_wav(self.root / "long.wav", duration=8)
        for path, text, issue in ((short, "这是需要完整朗读的句子。" * 10, "too_short"),
                                  (long, "你好", "too_long")):
            with self.subTest(issue=issue):
                self.assertIn(issue, inspect_wav(path, text)["issues"])


class ExportChaptersTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.destination = self.root / "export"

    def segment(self, identifier, *, chapter=1, index=0, duration=1, rate=8000,
                channels=1, text="你好", samples=None):
        relative = f"audio/{identifier}.wav"
        write_wav(self.root / relative, duration=duration, rate=rate,
                  channels=channels, samples=samples)
        return {"id": identifier, "chapter": chapter, "chapter_title": "../章节/标题",
                "index": index, "text": text, "status": "DONE", "audio_path": relative}

    def test_exports_ordered_samples_subtitles_and_provenance(self):
        first = self.segment("first", text="第一句")
        second = self.segment("second", index=1, duration=0.5, text="第二句")
        third = self.segment("third", chapter=2, duration=0.25, text="第三句")
        paths = export_chapters([second, third, first], self.root, self.destination, pause_ms=200)
        self.assertEqual(paths, [self.destination / "chapter-0001.wav",
                                 self.destination / "chapter-0002.wav"])
        with wave.open(str(paths[0]), "rb") as joined:
            self.assertEqual(joined.getnframes(), 13600)
            actual = joined.readframes(joined.getnframes())
        with wave.open(str(self.root / first["audio_path"]), "rb") as original:
            self.assertEqual(actual[:16000], original.readframes(8000))
        self.assertEqual(actual[16000:19200], bytes(3200))
        with wave.open(str(self.root / second["audio_path"]), "rb") as original:
            self.assertEqual(actual[19200:], original.readframes(4000))
        self.assertEqual(paths[0].with_suffix(".srt").read_text(),
                         "1\n00:00:00,000 --> 00:00:01,000\n第一句\n\n"
                         "2\n00:00:01,200 --> 00:00:01,700\n第二句\n\n")
        manifest = json.loads((self.destination / "manifest.json").read_text())
        self.assertEqual(manifest["chapters"][0]["title"], "../章节/标题")
        self.assertEqual(manifest["chapters"][0]["duration"], 1.7)
        source = manifest["chapters"][0]["segments"][0]
        self.assertEqual(source["id"], "first")
        self.assertEqual(source["start_frame"], 0)
        self.assertEqual(source["end_frame"], 8000)
        self.assertEqual(source["sha256"], hashlib.sha256((self.root / first["audio_path"]).read_bytes()).hexdigest())
        self.assertEqual((self.destination / "playlist.m3u").read_text(),
                         "#EXTM3U\nchapter-0001.wav\nchapter-0002.wav\n")

    def test_invalid_or_incomplete_input_keeps_existing_export(self):
        good = self.segment("good")
        export_chapters([good], self.root, self.destination)
        previous = {path.name: path.read_bytes() for path in self.destination.iterdir()}
        missing = dict(good, id="missing", audio_path="audio/missing.wav")
        corrupt = self.segment("corrupt")
        (self.root / corrupt["audio_path"]).write_bytes(b"RIFFbroken")
        incompatible = self.segment("other-rate", index=1, rate=16000)
        stereo = self.segment("stereo", index=1, channels=2)
        cases = ([], [dict(good, status="QA_REVIEW")], [missing], [corrupt],
                 [good, incompatible], [good, stereo])
        for index, segments in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                export_chapters(segments, self.root, self.destination)
            self.assertEqual({path.name: path.read_bytes() for path in self.destination.iterdir()}, previous)

    def test_done_segments_can_export_accepted_quality_findings(self):
        segment = self.segment("accepted", samples=[32767, -32768] * 4000)
        segment["review_accept"] = True
        paths = export_chapters([segment], self.root, self.destination)
        self.assertEqual(len(paths), 1)
        manifest = json.loads((self.destination / "manifest.json").read_text())
        source = manifest["chapters"][0]["segments"][0]
        self.assertIn("clipping", source["qa"]["issues"])
        self.assertTrue(source["source"]["review_accept"])

    def test_refuses_source_escape_or_export_over_project(self):
        segment = self.segment("source")
        outside = Path(self.temp.name) / "outside.wav"
        write_wav(outside)
        for path in ("../outside.wav", str(outside)):
            with self.subTest(path=path), self.assertRaises(ValueError):
                export_chapters([dict(segment, audio_path=path)], self.root, self.destination)
        with self.assertRaises(ValueError):
            export_chapters([segment], self.root, self.root)
        self.assertTrue((self.root / segment["audio_path"]).is_file())

    def test_refuses_negative_pause_without_creating_export(self):
        with self.assertRaises(ValueError):
            export_chapters([self.segment("voice")], self.root, self.destination, pause_ms=-1)
        self.assertFalse(self.destination.exists())

    def test_refuses_to_replace_unmanaged_directory_file_or_symlink(self):
        segment = self.segment("voice")
        unknown = self.root / "unrelated"
        unknown.mkdir()
        sentinel = unknown / "keep.txt"
        sentinel.write_text("keep me")
        plain_file = self.root / "file"
        plain_file.write_text("keep file")
        link = self.root / "link"
        link.symlink_to(unknown, target_is_directory=True)
        for destination in (unknown, plain_file, link):
            with self.subTest(destination=destination.name), self.assertRaises(ValueError):
                export_chapters([segment], self.root, destination)
        self.assertEqual(sentinel.read_text(), "keep me")
        self.assertEqual(plain_file.read_text(), "keep file")
        self.assertTrue(link.is_symlink())

    def test_successful_replacement_removes_obsolete_chapters(self):
        first = self.segment("first")
        second = self.segment("second", chapter=2)
        export_chapters([first, second], self.root, self.destination)
        paths = export_chapters([first], self.root, self.destination)
        self.assertEqual(len(paths), 1)
        self.assertFalse((self.destination / "chapter-0002.wav").exists())
        self.assertFalse((self.destination / "chapter-0002.srt").exists())
        self.assertEqual(len(json.loads((self.destination / "manifest.json").read_text())["chapters"]), 1)

    def test_failed_publication_restores_previous_complete_export(self):
        first = self.segment("first")
        export_chapters([first], self.root, self.destination)
        previous = {path.name: path.read_bytes() for path in self.destination.iterdir()}
        second = self.segment("second", chapter=2)
        real_replace = os.replace

        def fail_stage_publication(source, target):
            if Path(source).name.startswith(".raradio-export-"):
                raise OSError("simulated filesystem publication failure")
            return real_replace(source, target)

        with patch("raradio.audio.os.replace", side_effect=fail_stage_publication):
            with self.assertRaises(OSError):
                export_chapters([first, second], self.root, self.destination)
        self.assertEqual({path.name: path.read_bytes() for path in self.destination.iterdir()}, previous)
        self.assertEqual(list(self.root.glob(".raradio-*")), [])

    def test_does_not_remove_unrelated_files_added_to_an_export(self):
        segment = self.segment("voice")
        export_chapters([segment], self.root, self.destination)
        extra = self.destination / "listener-notes.txt"
        extra.write_text("my notes")
        with self.assertRaises(ValueError):
            export_chapters([segment], self.root, self.destination)
        self.assertEqual(extra.read_text(), "my notes")

    def test_cancelled_publication_restores_previous_complete_export(self):
        first = self.segment("first")
        export_chapters([first], self.root, self.destination)
        previous = {path.name: path.read_bytes() for path in self.destination.iterdir()}
        real_replace = os.replace

        def cancel_publication(source, target):
            if Path(source).name.startswith(".raradio-export-"):
                raise KeyboardInterrupt()
            return real_replace(source, target)

        with patch("raradio.audio.os.replace", side_effect=cancel_publication):
            with self.assertRaises(KeyboardInterrupt):
                export_chapters([first], self.root, self.destination)
        self.assertEqual({path.name: path.read_bytes() for path in self.destination.iterdir()}, previous)


if __name__ == "__main__":
    unittest.main()
