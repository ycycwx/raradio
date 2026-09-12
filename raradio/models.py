"""Shared data contracts; source text is immutable after ingestion."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Segment:
    id: str
    chapter: int
    chapter_title: str
    index: int
    start: int
    end: int
    text: str
    kind: str
    speaker_id: str | None = None
    confidence: float = 0.0
    emotion: str = "neutral"
    reason: str = ""
    parse_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    aliases: tuple[str, ...] = ()


@dataclass
class AnalysisResult:
    segments: list[Segment]
    characters: list[Character] = field(default_factory=list)


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    backend: str = "tone"
    model: str = ""
    reference_audio: str | None = None
    reference_text: str | None = None
    language: str = "Chinese"
    speaker: str | None = None
    instruct: str = ""
    speed: float = 1.0
    temperature: float = 0.7
    seed: int = 0
    clone_mode: str = "icl"
    emotion_mode: str = "strict"
