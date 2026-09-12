"""Source-preserving chapter detection and provisional speech segmentation.

Offsets count Python Unicode characters, not UTF-8 bytes. Whitespace between
segments may be omitted; all other source characters occur exactly once.
Chapter and dialogue detection are heuristics, not semantic interpretation.
"""

from bisect import bisect_left
import hashlib
import re
import unicodedata

from .models import Segment


_HEADING = re.compile(
    r"^(?:第[零〇一二三四五六七八九十百千万两壱弐参0-9０-９]+[章节節回卷巻部話]"
    r"|chapter\s+(?:\d+|[ivxlcdm]+)"
    r"|序章|序幕|楔子|终章|終章|尾声|後記|后记|前言|あとがき|まえがき"
    r"|prologue|epilogue)(?:\s+.*|[：:—–-].*)?$",
    re.IGNORECASE,
)
_QUOTES = {"“": "”", "「": "」", "『": "』", "‘": "’", '"': '"'}
_CLOSING_QUOTES = frozenset(_QUOTES.values())
_LINES = re.compile(r"[^\r\n]+|\r\n|[\r\n]")


def source_segment(text: str, start: int, end: int, *, chapter: int,
                   chapter_title: str, index: int, kind: str,
                   parse_issues: tuple[str, ...] = ()) -> Segment:
    """Build an exact source slice with an ID independent of annotations.

    This factory does not trim or normalize text. The caller owns chapter and
    speech decisions; a changed kind or chapter does not change source identity.
    """
    if not isinstance(text, str):
        raise ValueError("source text must be a string")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise ValueError("source segment range must satisfy 0 <= start < end <= source length")
    if _joined(text, start) or _joined(text, end):
        raise ValueError("source segment range splits a Unicode combining sequence")
    source = text[start:end]
    if not source.strip():
        raise ValueError("source segment must contain non-whitespace text")
    identity = hashlib.sha256(f"{start}:{end}:{source}".encode("utf-8")).hexdigest()[:16]
    return Segment(id=f"seg-{identity}", chapter=chapter, chapter_title=chapter_title,
                   index=index, start=start, end=end, text=source, kind=kind,
                   parse_issues=tuple(parse_issues))


def _quote_pairs(text: str) -> tuple[dict[int, int], dict[int, list[str]]]:
    """Pair delimiters first, so one missing close cannot consume the book."""
    stack: list[tuple[int, str]] = []
    pending = {closing: 0 for closing in _CLOSING_QUOTES}
    pairs: dict[int, int] = {}
    issues: dict[int, list[str]] = {}

    def report(offset: int, message: str) -> None:
        issues.setdefault(offset, []).append(f"{message} at source offset {offset}")

    for cursor, character in enumerate(text):
        if character == '"':
            previous = cursor - 1
            while previous >= 0 and text[previous] == "\\":
                previous -= 1
            if (cursor - previous - 1) % 2:
                continue
        if character == "’" and 0 < cursor < len(text) - 1:
            neighbors = text[cursor - 1] + text[cursor + 1]
            if neighbors.isascii() and neighbors.isalnum():
                continue
        if stack and character == stack[-1][1]:
            opening, closing = stack.pop()
            pending[closing] -= 1
            pairs[opening] = cursor + 1
        elif character in _QUOTES:
            stack.append((cursor, _QUOTES[character]))
            pending[_QUOTES[character]] += 1
        elif character in _CLOSING_QUOTES:
            # A close matching an ancestor ends that quote and reports any
            # intervening malformed nesting. A stray close stays source text.
            if not pending[character]:
                report(cursor, f"Unexpected closing quote {character!r}")
                continue
            report(cursor, f"Mismatched closing quote {character!r}")
            while stack[-1][1] != character:
                opening, closing = stack.pop()
                pending[closing] -= 1
                report(opening, f"Unclosed quote; expected {closing!r}")
            opening, closing = stack.pop()
            pending[closing] -= 1
            pairs[opening] = cursor + 1
    for opening, closing in stack:
        report(opening, f"Unclosed quote; expected {closing!r}")
    return pairs, issues


def _joined(text: str, offset: int) -> bool:
    """Protect marks, variation selectors, emoji modifiers and ZWJ chains.

    This deliberately covers common combining sequences, not full Unicode
    grapheme segmentation (for example, regional-indicator pairing or Hangul).
    """
    if not 0 < offset < len(text):
        return False
    character = text[offset]
    return (unicodedata.category(character).startswith("M")
            or character == "\u200d" or text[offset - 1] == "\u200d"
            or "\U0001f3fb" <= character <= "\U0001f3ff")


def split_text(text: str, max_chars: int = 240, *, chapter_mode: str = "auto") -> list[Segment]:
    """Split immutable source into bounded, provisional speech slices.

    Chapters and segment indexes are one-based and zero-based respectively.
    Well-formed nested/multiline quotes stay dialogue. Malformed delimiters are
    preserved and reported in parse_issues; unmatched opens do not claim all
    following text as dialogue. Heading lines are spoken narration. Set
    chapter_mode='none' when the manuscript should stay in one chapter.

    The same source and options yield the same IDs. Chunking preserves common
    combining sequences without normalizing source; a sequence longer than the
    limit raises ValueError instead of silently splitting it.
    """
    if not isinstance(text, str):
        raise ValueError("source text must be a string")
    if type(max_chars) is not int or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    if chapter_mode not in ("auto", "none"):
        raise ValueError("chapter_mode must be 'auto' or 'none'")

    pairs, issues = _quote_pairs(text)
    issue_offsets = sorted(issues)
    segments: list[Segment] = []
    chapter, chapter_title = 1, "Main text"

    def emit(start: int, end: int, kind: str) -> None:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        while start < end:
            stop = min(start + max_chars, end)
            if stop < end:
                # Prefer a sentence or word break in the latter half.
                for candidate in range(stop, start + max_chars // 2, -1):
                    if text[candidate - 1] in "。！？!?；;，,、. \t\r\n" and not _joined(text, candidate):
                        stop = candidate
                        break
                while stop > start and _joined(text, stop):
                    stop -= 1
                if stop == start:
                    raise ValueError(f"Unicode combining sequence at source offset {start} exceeds max_chars={max_chars}")
            trimmed = stop
            while trimmed > start and text[trimmed - 1].isspace():
                trimmed -= 1
            if trimmed > start:
                first = bisect_left(issue_offsets, start)
                last = bisect_left(issue_offsets, trimmed)
                segment_issues = tuple(message for offset in issue_offsets[first:last] for message in issues[offset])
                segments.append(source_segment(text, start, trimmed, chapter=chapter,
                                               chapter_title=chapter_title, index=len(segments),
                                               kind=kind, parse_issues=segment_issues))
            start = stop
            while start < end and text[start].isspace():
                start += 1

    # Index physical lines once, preserving LF, CRLF and CR source offsets.
    lines = {match.start(): match.end() for match in _LINES.finditer(text)
             if text[match.start()] not in "\r\n"}
    start = cursor = 0
    while cursor < len(text):
        if chapter_mode == "auto" and cursor in lines:
            line_end = lines[cursor]
            title = text[cursor:line_end].strip()
            if _HEADING.fullmatch(title):
                emit(start, cursor, "narration")
                if segments:
                    chapter += 1
                chapter_title = title
                emit(cursor, line_end, "narration")
                cursor = line_end
                start = cursor
                continue
        if cursor in pairs:
            emit(start, cursor, "narration")
            end = pairs[cursor]
            emit(cursor, end, "dialogue")
            start = cursor = end
            continue
        if text[cursor] in "\r\n":
            emit(start, cursor, "narration")
            start = cursor + 1
        cursor += 1
    emit(start, len(text), "narration")
    return segments
