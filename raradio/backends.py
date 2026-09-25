"""Synthesis adapters. The tone backend produces diagnostic beeps, never speech."""

from __future__ import annotations

from array import array
import hashlib
from importlib import import_module, metadata
import math
from pathlib import Path
import sys
from typing import Iterable, Protocol
import wave

from .models import VoiceProfile


class Backend(Protocol):
    version: str

    def synthesize(
        self, text: str, voice: VoiceProfile, emotion: str, output: Path
    ) -> None: ...


def _validate_input(text: str, voice: VoiceProfile) -> None:
    if not text.strip():
        raise ValueError("Synthesis text must not be empty")
    if not math.isfinite(voice.speed) or voice.speed <= 0:
        raise ValueError("Voice speed must be finite and positive")


def _write_pcm(output: Path, samples: Iterable[float], sample_rate: int = 24000) -> None:
    pcm = array("h")
    for sample in samples:
        if not math.isfinite(sample):
            raise ValueError("Backend produced non-finite audio samples")
        pcm.append(max(-32768, min(32767, round(sample * 32768))))
    if not pcm:
        raise ValueError("Backend produced no audio")
    if sys.byteorder != "little":
        pcm.byteswap()
    with wave.open(str(output), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(pcm.tobytes())


class ToneBackend:
    """Deterministic diagnostic sine waveform for testing the render pipeline."""

    version = "tone-diagnostic-v1"

    def synthesize(
        self, text: str, voice: VoiceProfile, emotion: str, output: Path
    ) -> None:
        _validate_input(text, voice)
        frequency = 220 + int(hashlib.sha256(voice.id.encode()).hexdigest()[:4], 16) % 220
        count = max(1, sum(not char.isspace() for char in text))
        duration = max(0.4, count * 0.13) / voice.speed
        _write_pcm(
            output,
            (0.18 * math.sin(2 * math.pi * frequency * index / 24000)
             for index in range(round(duration * 24000))),
        )


class MlxBackend:
    """Qwen3-TTS Base cloning and CustomVoice adapters; imports MLX on first use.

    A backend retains one loaded model, avoiding repeated loads for adjacent
    segments without keeping every cast model in GPU memory simultaneously.
    """

    def __init__(self) -> None:
        self._model = None
        self._model_path = None
        self._dependency_failure: str | None = None
        try:
            package_version = metadata.version("mlx-audio")
        except metadata.PackageNotFoundError:
            package_version = "not-installed"
        self.version = f"mlx-qwen3-pcm16-v2/mlx-audio-{package_version}"

    def _load(self, model_path: str):
        if self._dependency_failure is not None:
            raise RuntimeError(self._dependency_failure)
        try:
            core = import_module("mlx.core")
            utils = import_module("mlx_audio.tts.utils")
        except ImportError as error:
            # A failed native import can leave extension types registered.
            # Retrying it in this process may abort, rather than raise Python errors.
            self._dependency_failure = (
                f"MLX backend could not initialize: {error}. "
                "Requires the pinned mlx-audio[tts] dependency and Apple Silicon with Metal GPU access. "
                "If installed, check Metal availability and sandbox GPU permissions. "
                "Restart the process after correcting the environment."
            )
            raise RuntimeError(self._dependency_failure) from error
        if self._model_path != model_path:
            self._model = None
            self._model_path = None
            self._model = utils.load_model(model_path)
            self._model_path = model_path
        return core, self._model

    def synthesize(
        self, text: str, voice: VoiceProfile, emotion: str, output: Path
    ) -> None:
        _validate_input(text, voice)
        if not voice.model.strip():
            raise ValueError("MLX voice requires an explicit model path or repository ID")
        if voice.speed != 1.0:
            raise ValueError("Qwen3-TTS does not support speed changes; set speed to 1.0")
        if not math.isfinite(voice.temperature) or voice.temperature < 0:
            raise ValueError("Voice temperature must be finite and non-negative")
        if voice.emotion_mode not in {"strict", "reference"}:
            raise ValueError("Voice emotion_mode must be 'strict' or 'reference'")
        core, model = self._load(voice.model)
        if getattr(model, "model_type", None) != "qwen3_tts":
            raise ValueError("MLX adapter supports Qwen3-TTS models only")
        model_type = model.config.tts_model_type
        if model_type not in {"base", "custom_voice"}:
            raise ValueError("MLX adapter supports Base and CustomVoice models only")
        languages = {language.lower() for language in model.get_supported_languages()}
        if voice.language.lower() not in languages:
            raise ValueError(f"Unsupported Qwen3-TTS language: {voice.language!r}")
        if model.sample_rate != 24000:
            raise ValueError("Qwen3-TTS model must output 24000 Hz audio")
        characters = sum(not char.isspace() for char in text)
        request = dict(
            text=text,
            temperature=voice.temperature,
            max_tokens=max(96, min(2048, characters * 6 + 96)),
            top_k=50,
            top_p=0.9,
            repetition_penalty=1.1,
            verbose=False,
            stream=False,
        )
        if model_type == "base":
            if voice.speaker:
                raise ValueError("Base models have no preset speaker; use reference audio")
            if voice.instruct.strip():
                raise ValueError("Base cloning does not support instruction control")
            if voice.emotion_mode == "strict" and emotion.strip().lower() not in {"", "neutral"}:
                raise ValueError("Base cloning does not support emotion control")
            if not voice.reference_audio or not Path(voice.reference_audio).is_file():
                raise ValueError("Base cloning requires an existing reference audio file")
            if getattr(model, "speaker_encoder", None) is None:
                raise ValueError("Base cloning requires a speaker encoder")
            if voice.clone_mode == "icl":
                if not voice.reference_text or not voice.reference_text.strip():
                    raise ValueError("Base ICL cloning requires the reference audio transcript")
                if not getattr(model.speech_tokenizer, "has_encoder", False):
                    raise ValueError("Base ICL cloning requires a speech tokenizer encoder")
                reference_text = voice.reference_text
            elif voice.clone_mode == "xvector":
                if voice.reference_text:
                    raise ValueError("Base xvector cloning does not use a transcript; omit reference_text")
                reference_text = None
            else:
                raise ValueError("Base clone_mode must be 'icl' or 'xvector'")
            request.update(
                ref_audio=str(Path(voice.reference_audio).resolve()),
                ref_text=reference_text,
                voice=None,
                lang_code=voice.language,
                split_pattern="",
            )
            generate = model.generate
        else:
            if voice.emotion_mode != "strict":
                raise ValueError("CustomVoice does not support reference emotion_mode; use 'strict'")
            if voice.reference_audio or voice.reference_text:
                raise ValueError("CustomVoice cannot use reference audio or a reference transcript")
            if voice.clone_mode != "icl":
                raise ValueError("CustomVoice does not support clone_mode; use the default value")
            speakers = model.get_supported_speakers()
            if not voice.speaker or voice.speaker.lower() not in {
                speaker.lower() for speaker in speakers
            }:
                raise ValueError(f"Unsupported CustomVoice speaker: {voice.speaker!r}; available: {speakers}")
            instructions = [voice.instruct.strip()]
            if emotion.strip().lower() not in {"", "neutral"}:
                instructions.append(f"Emotion: {emotion.strip()}.")
            request.update(
                speaker=voice.speaker,
                language=voice.language,
                instruct="\n".join(part for part in instructions if part) or None,
            )
            generate = model.generate_custom_voice
        core.random.seed(voice.seed)

        def samples():
            for result in generate(**request):
                if result.token_count >= request["max_tokens"]:
                    raise ValueError("Backend reached its token limit; speech may be truncated")
                if result.sample_rate != 24000 or result.audio.ndim != 1:
                    raise ValueError("Backend produced audio with an unexpected sample rate or channel shape")
                yield from result.audio.tolist()

        _write_pcm(output, samples())


def get_backend(name: str) -> Backend:
    if name == "tone":
        return ToneBackend()
    if name == "mlx":
        return MlxBackend()
    raise ValueError(f"Unknown TTS backend: {name!r}")
