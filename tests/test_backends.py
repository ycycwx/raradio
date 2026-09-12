"""Backend contracts: usable PCM output and no silent setting/voice fallback."""

from dataclasses import replace
from importlib import import_module
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from raradio.models import VoiceProfile


class ToneBackendTests(unittest.TestCase):
    def test_tone_writes_reproducible_audible_mono_pcm16(self):
        # Catches empty output, float WAV output, and nondeterministic test renders.
        from raradio.backends import get_backend

        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "first.wav", Path(folder) / "second.wav"
            profile = VoiceProfile("diagnostic")
            backend = get_backend("tone")
            backend.synthesize("测试声音。", profile, "neutral", first)
            backend.synthesize("测试声音。", profile, "neutral", second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with wave.open(str(first), "rb") as audio:
                self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (1, 2, 24000))
                self.assertGreater(audio.getnframes(), 2400)
                frames = audio.readframes(audio.getnframes())
                self.assertTrue(any(struct.unpack("<" + "h" * (len(frames) // 2), frames)))

    def test_unknown_backend_fails_instead_of_rendering_a_default_voice(self):
        from raradio.backends import get_backend

        with self.assertRaisesRegex(ValueError, "backend"):
            get_backend("typo")

    def test_invalid_speed_or_empty_text_never_creates_output(self):
        from raradio.backends import get_backend

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "audio.wav"
            for text, speed in [(" ", 1), ("测试", 0), ("测试", float("nan"))]:
                with self.subTest(text=text, speed=speed):
                    with self.assertRaises(ValueError):
                        get_backend("tone").synthesize(text, VoiceProfile("test", speed=speed), "neutral", output)
                    self.assertFalse(output.exists())


class FakeAudio:
    """Only substitutes the heavy MLX array produced by inference."""

    def __init__(self, samples):
        self.samples = samples
        self.ndim = 1

    def tolist(self):
        return self.samples


def generation_result(samples, sample_rate=24000):
    return SimpleNamespace(
        audio=FakeAudio(samples), samples=len(samples), sample_rate=sample_rate,
        segment_idx=0, token_count=1, audio_duration="00:00:00.001",
        real_time_factor=1.0, prompt={}, audio_samples={},
        processing_time_seconds=0.001, peak_memory_usage=0.0,
        is_streaming_chunk=False, is_final_chunk=False,
    )


class MlxBackendTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.output = Path(self.folder.name) / "speech.wav"
        self.reference = (Path(self.folder.name) / "reference.wav").resolve()
        with wave.open(str(self.reference), "wb") as audio:
            audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            audio.writeframes(struct.pack("<hhhh", 0, 100, -100, 0))
        self.requests, self.loaded, self.seeds = [], [], []
        self.results = [generation_result([-1, -0.5, 0]), generation_result([0.5, 1])]
        self.model = SimpleNamespace(
            model_type="qwen3_tts", sample_rate=24000,
            config=SimpleNamespace(tts_model_type="custom_voice"),
            get_supported_speakers=lambda: ["vivian", "ryan"],
            get_supported_languages=lambda: ["auto", "chinese", "english"],
            speech_tokenizer=SimpleNamespace(has_encoder=True),
            speaker_encoder=object(),
            generate=self.generate, generate_custom_voice=self.generate,
        )
        modules = {
            "mlx": SimpleNamespace(),
            "mlx.core": SimpleNamespace(random=SimpleNamespace(seed=self.seeds.append)),
            "mlx_audio": SimpleNamespace(),
            "mlx_audio.tts": SimpleNamespace(),
            "mlx_audio.tts.utils": SimpleNamespace(load_model=self.load_model),
        }
        self.patcher = patch.dict(sys.modules, modules)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.profile = VoiceProfile("vivian", backend="mlx", model="model-snapshot", speaker="Vivian", seed=42)

    def load_model(self, path):
        self.loaded.append(path)
        return self.model

    def generate(self, **kwargs):
        self.requests.append(kwargs)
        return iter(self.results)

    def test_custom_voice_preserves_speaker_style_language_seed_and_pcm_samples(self):
        # Catches routing to Base, dropping controls, wrong signed PCM, or losing chunks.
        from raradio.backends import get_backend

        backend = get_backend("mlx")
        self.assertEqual(self.loaded, [])
        profile = replace(self.profile, instruct="轻声朗读。", temperature=0.6)
        backend.synthesize("你好。", profile, "happy", self.output)
        backend.synthesize("再见。", profile, "neutral", self.output)
        self.assertEqual(self.loaded, ["model-snapshot"])
        self.assertEqual(self.seeds, [42, 42])
        request = self.requests[0]
        self.assertEqual(request["speaker"], "Vivian")
        self.assertEqual(request["language"], "Chinese")
        self.assertEqual(request["temperature"], 0.6)
        self.assertEqual(request["text"], "你好。")
        self.assertIn("轻声朗读。", request["instruct"])
        self.assertIn("happy", request["instruct"])
        self.assertNotIn("ref_audio", request)
        with wave.open(str(self.output), "rb") as audio:
            self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (1, 2, 24000))
            self.assertEqual(struct.unpack("<hhhhh", audio.readframes(5)), (-32768, -16384, 0, 16384, 32767))

    def test_base_uses_validated_reference_with_transcript(self):
        from raradio.backends import get_backend

        self.model.config.tts_model_type = "base"
        profile = replace(self.profile, speaker=None, reference_audio=str(self.reference), reference_text="参考录音。")
        get_backend("mlx").synthesize("正文。", profile, "neutral", self.output)
        request = self.requests[0]
        self.assertEqual(request["ref_audio"], str(self.reference))
        self.assertEqual(request["ref_text"], "参考录音。")
        self.assertEqual(request["lang_code"], "Chinese")
        self.assertEqual(request["split_pattern"], "")
        self.assertIsNone(request["voice"])
        self.assertNotIn("instruct", request)
        self.assertTrue(self.output.is_file())

    def test_invalid_or_unsupported_settings_fail_before_inference(self):
        # Catches silent speaker/language fallback and ignored emotion, speed or refs.
        from raradio.backends import get_backend

        clone = replace(self.profile, speaker=None, reference_audio=str(self.reference), reference_text="参考。")
        cases = [
            ("custom_voice", replace(self.profile, speaker="typo"), "neutral", "speaker"),
            ("custom_voice", replace(self.profile, language="typo"), "neutral", "language"),
            ("custom_voice", replace(self.profile, speaker=None), "neutral", "speaker"),
            ("custom_voice", replace(self.profile, reference_audio=str(self.reference)), "neutral", "reference"),
            ("custom_voice", replace(self.profile, clone_mode="xvector"), "neutral", "clone_mode"),
            ("custom_voice", replace(self.profile, speed=1.2), "neutral", "speed"),
            ("custom_voice", replace(self.profile, temperature=float("nan")), "neutral", "temperature"),
            ("custom_voice", replace(self.profile, model=""), "neutral", "model"),
            ("base", clone, "sad", "emotion"),
            ("base", replace(clone, instruct="悲伤地说"), "neutral", "instruction"),
            ("base", replace(clone, reference_text=None), "neutral", "transcript"),
            ("base", replace(clone, reference_audio=str(self.reference) + "missing"), "neutral", "reference"),
            ("base", replace(clone, reference_audio=None), "neutral", "reference"),
            ("base", replace(clone, speaker="Vivian"), "neutral", "speaker"),
            ("base", replace(clone, clone_mode="typo"), "neutral", "clone_mode"),
            ("base", replace(clone, clone_mode="xvector"), "neutral", "transcript"),
            ("voice_design", self.profile, "neutral", "model"),
        ]
        for index, (model_type, profile, emotion, message) in enumerate(cases):
            with self.subTest(model_type=model_type, profile=profile, emotion=emotion):
                self.model.config.tts_model_type = model_type
                output = self.output.with_name(f"invalid-{index}.wav")
                with self.assertRaisesRegex(ValueError, message):
                    get_backend("mlx").synthesize("正文。", profile, emotion, output)
                self.assertFalse(output.exists())
        self.assertEqual(self.requests, [])

    def test_invalid_audio_does_not_leave_a_plausible_output(self):
        from raradio.backends import get_backend

        for results in [[], [generation_result([])], [generation_result([float("nan")])], [generation_result([0.1], 16000)]]:
            with self.subTest(results=results):
                self.results = results
                with self.assertRaisesRegex(ValueError, "audio"):
                    get_backend("mlx").synthesize("正文。", self.profile, "neutral", self.output)
                self.assertFalse(self.output.exists())

    def test_base_rejects_tokenizer_without_clone_encoder(self):
        from raradio.backends import get_backend

        self.model.config.tts_model_type = "base"
        self.model.speech_tokenizer.has_encoder = False
        clone = replace(self.profile, speaker=None, reference_audio=str(self.reference), reference_text="参考。")
        with self.assertRaisesRegex(ValueError, "encoder"):
            get_backend("mlx").synthesize("正文。", clone, "neutral", self.output)
        self.assertFalse(self.output.exists())

    def test_missing_optional_dependency_has_actionable_error_without_output(self):
        from raradio.backends import get_backend

        with patch.dict(sys.modules, {"mlx.core": None}):
            with self.assertRaisesRegex(RuntimeError, "mlx-audio"):
                get_backend("mlx").synthesize("正文。", self.profile, "neutral", self.output)
        self.assertFalse(self.output.exists())

    def test_dependency_import_failure_is_not_retried_on_a_partially_initialized_runtime(self):
        # Reimporting a failed native MLX extension can abort the entire process.
        from raradio.backends import get_backend

        for failed_module in ["mlx.core", "mlx_audio.tts.utils"]:
            with self.subTest(failed_module=failed_module):
                imports = []

                def import_dependency(name):
                    imports.append(name)
                    if name == failed_module:
                        raise ImportError("[metal::load_device] No Metal device available")
                    return import_module(name)

                backend = get_backend("mlx")
                with patch("raradio.backends.import_module", side_effect=import_dependency):
                    for text in ["首次尝试。", "重试。", "下个片段。"]:
                        with self.assertRaises(RuntimeError):
                            backend.synthesize(text, self.profile, "neutral", self.output)
                expected = ["mlx.core"] if failed_module == "mlx.core" else ["mlx.core", "mlx_audio.tts.utils"]
                self.assertEqual(imports, expected)
                self.assertFalse(self.output.exists())

    def test_dependency_error_exposes_original_gpu_failure_on_every_attempt(self):
        from raradio.backends import get_backend

        backend = get_backend("mlx")
        failure = ImportError("[metal::load_device] No Metal device available; sandboxed process")
        with patch("raradio.backends.import_module", side_effect=failure):
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, "No Metal device available; sandboxed process"):
                    backend.synthesize("正文。", self.profile, "neutral", self.output)
        self.assertFalse(self.output.exists())

    def test_xvector_uses_reference_without_transcript_or_tokenizer_encoder(self):
        # Catches accidentally switching cross-language xvector cloning to ICL.
        from raradio.backends import get_backend

        self.model.config.tts_model_type = "base"
        self.model.speech_tokenizer.has_encoder = False
        clone = replace(self.profile, speaker=None, reference_audio=str(self.reference), clone_mode="xvector")
        get_backend("mlx").synthesize("这是中文。", clone, "neutral", self.output)
        self.assertEqual(self.requests[0]["ref_audio"], str(self.reference))
        self.assertIsNone(self.requests[0]["ref_text"])
        self.assertIsNone(self.requests[0]["voice"])
        self.assertEqual(self.requests[0]["lang_code"], "Chinese")
        self.assertTrue(self.output.exists())

    def test_xvector_never_falls_back_when_speaker_encoder_is_missing(self):
        from raradio.backends import get_backend

        self.model.config.tts_model_type = "base"
        self.model.speaker_encoder = None
        clone = replace(self.profile, speaker=None, reference_audio=str(self.reference), clone_mode="xvector")
        with self.assertRaisesRegex(ValueError, "speaker encoder"):
            get_backend("mlx").synthesize("正文。", clone, "neutral", self.output)
        self.assertFalse(self.output.exists())

    def test_token_limit_exhaustion_fails_instead_of_publishing_truncated_speech(self):
        from raradio.backends import get_backend

        result = generation_result([0.1, -0.1])
        result.token_count = 100000
        self.results = [result]
        with self.assertRaisesRegex(ValueError, "token limit"):
            get_backend("mlx").synthesize("正文。", self.profile, "neutral", self.output)
        self.assertFalse(self.output.exists())

    def test_reference_emotion_policy_keeps_clone_request_and_text_for_any_annotation(self):
        # Catches leaking analytical emotion into unsupported Base instructions.
        from raradio.backends import get_backend

        self.model.config.tts_model_type = "base"
        clone = replace(
            self.profile, speaker=None, reference_audio=str(self.reference),
            reference_text="参考文本。", emotion_mode="reference",
        )
        backend = get_backend("mlx")
        for emotion in ["happy", "sad"]:
            backend.synthesize("她说：你好。", clone, emotion, self.output)
        self.assertEqual(self.requests[0], self.requests[1])
        self.assertEqual(self.requests[0]["text"], "她说：你好。")
        self.assertEqual(self.requests[0]["ref_audio"], str(self.reference))
        self.assertEqual(self.requests[0]["ref_text"], "参考文本。")
        self.assertNotIn("instruct", self.requests[0])
        self.assertNotIn("emotion", self.requests[0])
        self.assertTrue(self.output.exists())

    def test_reference_emotion_policy_supports_xvector_cloning(self):
        from raradio.backends import get_backend

        self.model.config.tts_model_type = "base"
        clone = replace(
            self.profile, speaker=None, reference_audio=str(self.reference),
            clone_mode="xvector", emotion_mode="reference",
        )
        get_backend("mlx").synthesize("她说：你好。", clone, "happy", self.output)
        self.assertEqual(self.requests[0]["text"], "她说：你好。")
        self.assertIsNone(self.requests[0]["ref_text"])
        self.assertNotIn("instruct", self.requests[0])
        self.assertTrue(self.output.exists())

    def test_emotion_policy_rejects_unknown_modes_and_custom_voice_reference_mode(self):
        from raradio.backends import get_backend

        cases = [
            ("custom_voice", replace(self.profile, emotion_mode="reference")),
            ("custom_voice", replace(self.profile, emotion_mode="typo")),
            ("base", replace(self.profile, emotion_mode="typo")),
        ]
        for model_type, profile in cases:
            with self.subTest(model_type=model_type, policy=profile.emotion_mode):
                self.model.config.tts_model_type = model_type
                with self.assertRaisesRegex(ValueError, "emotion_mode"):
                    get_backend("mlx").synthesize("正文。", profile, "neutral", self.output)
                self.assertFalse(self.output.exists())

    def test_reference_emotion_policy_still_rejects_instructions(self):
        from raradio.backends import get_backend

        self.model.config.tts_model_type = "base"
        clone = replace(
            self.profile, speaker=None, reference_audio=str(self.reference),
            reference_text="参考文本。", emotion_mode="reference", instruct="笑着说。",
        )
        with self.assertRaisesRegex(ValueError, "instruction"):
            get_backend("mlx").synthesize("正文。", clone, "happy", self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
