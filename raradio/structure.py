"""Reviewable source spans; humans may change boundaries, never the manuscript."""

import hashlib
import json

from .script import source_segment


_FIELDS = {"start", "end", "text", "chapter", "chapter_title", "kind"}


def structure_document(source_sha256, segments):
    entries = [{key: segment[key] for key in sorted(_FIELDS)} for segment in segments]
    encoded = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {"source_sha256": source_sha256, "revision": hashlib.sha256(encoded).hexdigest(),
            "segments": entries}


def validate_structure(document, current, text, max_chars):
    """Validate the entire replacement before a caller changes durable state."""
    if not isinstance(document, dict) or set(document) != {"source_sha256", "revision", "segments"}:
        raise ValueError("Structure requires source_sha256, revision and segments")
    if document["source_sha256"] != current["source_sha256"]:
        raise ValueError("Structure belongs to a different source")
    if document["revision"] != current["revision"]:
        raise ValueError("Structure is stale; export the current structure and apply the edits again")
    entries = document["segments"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("Structure segments must be a nonempty array")
    result = []
    cursor, chapter, title = 0, 0, None
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != _FIELDS:
            raise ValueError("Each structure segment requires start, end, text, chapter, chapter_title and kind")
        start, end, number = entry["start"], entry["end"], entry["chapter"]
        if type(start) is not int or type(end) is not int or not cursor <= start < end <= len(text):
            raise ValueError("Structure spans must be ordered, non-overlapping source offsets")
        if text[cursor:start].strip() or entry["text"] != text[start:end]:
            raise ValueError("Structure may not drop or rewrite source text")
        if not entry["text"].strip() or end - start > max_chars:
            raise ValueError("Structure spans must contain text and fit the project's max-chars limit")
        if type(number) is not int or number not in {chapter, chapter + 1} or number < 1:
            raise ValueError("Structure chapters must start at 1 and increase without gaps")
        if not isinstance(entry["chapter_title"], str) or not entry["chapter_title"].strip():
            raise ValueError("Structure chapter titles must be nonempty strings")
        if number == chapter and entry["chapter_title"] != title:
            raise ValueError("Segments in the same chapter must have the same title")
        if entry["kind"] not in ("narration", "dialogue"):
            raise ValueError("Structure kind must be narration or dialogue")
        result.append(source_segment(text, start, end, chapter=number,
                                     chapter_title=entry["chapter_title"], index=index, kind=entry["kind"]))
        cursor, chapter, title = end, number, entry["chapter_title"]
    if text[cursor:].strip():
        raise ValueError("Structure may not drop the end of the source")
    return result
