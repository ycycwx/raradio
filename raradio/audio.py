"""WAV inspection and chapter export without third-party dependencies."""

from array import array
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
import wave


def inspect_wav(path: Path, text: str) -> dict:
    """Measure a PCM WAV; return quality findings without accepting them."""
    try:
        with wave.open(str(path), "rb") as source:
            frames, rate, channels = source.getnframes(), source.getframerate(), source.getnchannels()
            if source.getcomptype() != "NONE" or source.getsampwidth() != 2:
                raise ValueError("Audio must be uncompressed PCM16 WAV")
            if frames <= 0 or rate <= 0 or channels <= 0:
                raise ValueError("Audio contains no readable samples")
            byte_count = sample_count = active_count = clipped_count = square_sum = 0
            while block := source.readframes(32768):
                if len(block) % (channels * 2):
                    raise ValueError("Audio ends in a truncated PCM frame")
                byte_count += len(block)
                samples = array("h", block)
                if sys.byteorder != "little":
                    samples.byteswap()
                sample_count += len(samples)
                for sample in samples:
                    square_sum += sample * sample
                    active_count += abs(sample) >= 64
                    clipped_count += abs(sample) >= 32760
            if byte_count != frames * channels * 2:
                raise ValueError("Audio sample data is truncated")
    except (OSError, EOFError, wave.Error) as error:
        raise ValueError(f"Cannot read WAV {path}: {error}") from error

    issues = []
    if square_sum / sample_count < 16 ** 2:
        issues.append("silence")
    elif active_count / sample_count < 0.01:
        issues.append("sparse_signal")
    if clipped_count / sample_count > 0.001:
        issues.append("clipping")
    duration = frames / rate
    characters = sum(not character.isspace() for character in text)
    if duration < max(0.08, characters / 30 - 0.3):
        issues.append("too_short")
    if duration > max(3, characters / 1.2 + 2):
        issues.append("too_long")
    return {"duration": duration, "sample_rate": rate, "channels": channels, "issues": issues}


def export_chapters(segments: list[dict], root: Path, destination: Path,
                    pause_ms: int = 180) -> list[Path]:
    """Publish complete chapters after validating all DONE source audio.

    DONE is the caller's approval boundary: quality warnings remain in the
    manifest, including findings a listener has explicitly accepted. A WAV
    that cannot be structurally decoded is always refused. The caller must
    verify that source hashes and voice configuration are still current.
    """
    if not segments:
        raise ValueError("No segments to export")
    if not isinstance(pause_ms, int) or pause_ms < 0:
        raise ValueError("pause_ms must be a nonnegative integer")
    root, destination = Path(root).resolve(), Path(destination)
    resolved_destination = destination.resolve()
    if resolved_destination == root or resolved_destination in root.parents:
        raise ValueError("Export destination cannot replace the project")
    _validate_destination(destination)

    prepared = []
    common_format = None
    for segment in sorted(segments, key=lambda item: (item["chapter"], item["index"])):
        if segment.get("status") != "DONE":
            raise ValueError(f"Segment {segment.get('id')} is not DONE; partial export refused")
        relative = Path(segment.get("audio_path") or "")
        path = (root / relative).resolve()
        if relative.is_absolute() or root not in path.parents:
            raise ValueError("Audio path must stay inside the project")
        if resolved_destination == path or resolved_destination in path.parents:
            raise ValueError("Export destination cannot replace source audio")
        qa = inspect_wav(path, segment["text"])
        audio_format = (qa["sample_rate"], qa["channels"])
        if common_format is not None and common_format != audio_format:
            raise ValueError("All source WAVs must have the same sample rate and channels")
        common_format = audio_format
        with wave.open(str(path), "rb") as source:
            frames = source.getnframes()
        prepared.append((dict(segment), path, qa, frames, _sha256(path)))

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".raradio-export-", dir=destination.parent))
    chapter_files = []
    manifest = {"schema_version": 1, "generator": "raradio", "pause_ms": pause_ms, "chapters": []}
    try:
        chapters = {}
        for entry in prepared:
            chapters.setdefault(entry[0]["chapter"], []).append(entry)
        rate, channels = common_format
        gap_frames = round(rate * pause_ms / 1000)
        for ordinal, (chapter, entries) in enumerate(chapters.items(), 1):
            filename = f"chapter-{ordinal:04d}.wav"
            chapter_files.append(filename)
            record = {"chapter": chapter, "title": entries[0][0]["chapter_title"],
                      "audio": filename, "subtitles": Path(filename).with_suffix(".srt").name,
                      "sample_rate": rate, "channels": channels, "segments": []}
            subtitles = []
            cursor = 0
            with wave.open(str(stage / filename), "wb") as output:
                output.setnchannels(channels)
                output.setsampwidth(2)
                output.setframerate(rate)
                for index, (segment, path, qa, frames, digest) in enumerate(entries):
                    if index:
                        remaining = gap_frames
                        while remaining:
                            count = min(remaining, 32768)
                            output.writeframesraw(bytes(count * channels * 2))
                            remaining -= count
                        cursor += gap_frames
                    start = cursor
                    copied = 0
                    with wave.open(str(path), "rb") as source:
                        while block := source.readframes(32768):
                            output.writeframesraw(block)
                            copied += len(block)
                    if copied != frames * channels * 2 or _sha256(path) != digest:
                        raise ValueError(f"Source audio changed during export: {path}")
                    cursor += frames
                    record["segments"].append({
                        "id": segment["id"], "index": segment["index"], "text": segment["text"],
                        "audio_path": segment["audio_path"], "sha256": digest,
                        "start_frame": start, "end_frame": cursor, "frames": frames,
                        "start": start / rate, "end": cursor / rate, "qa": qa, "source": segment})
                    text = " ".join(segment["text"].split())
                    subtitles.append(f"{index + 1}\n{_srt_time(start, rate)} --> {_srt_time(cursor, rate)}\n{text}\n\n")
            record.update({"frames": cursor, "duration": cursor / rate})
            (stage / record["subtitles"]).write_text("".join(subtitles), encoding="utf-8")
            manifest["chapters"].append(record)
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "playlist.m3u").write_text("#EXTM3U\n" + "\n".join(chapter_files) + "\n", encoding="utf-8")
        _publish_directory(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return [destination / filename for filename in chapter_files]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _srt_time(frames: int, rate: int) -> str:
    # Derive every timestamp from total sample counts to avoid cumulative drift.
    milliseconds = (frames * 1000 + rate // 2) // rate
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _publish_directory(stage: Path, destination: Path) -> None:
    _validate_destination(destination)
    backup = destination.with_name(f".raradio-backup-{uuid.uuid4().hex}")
    previous = destination.exists()
    if previous:
        os.replace(destination, backup)
    try:
        os.replace(stage, destination)
    except BaseException:
        if previous:
            os.replace(backup, destination)
        raise
    if previous:
        shutil.rmtree(backup)


def _validate_destination(destination: Path) -> None:
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError("Export destination must be a directory, not a file or symlink")
    if not destination.exists() or not any(destination.iterdir()):
        return
    try:
        manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        if manifest["generator"] != "raradio" or manifest["schema_version"] != 1:
            raise ValueError("Unrecognized export manifest")
        expected = {"manifest.json", "playlist.m3u"}
        for chapter in manifest["chapters"]:
            expected.update((chapter["audio"], chapter["subtitles"]))
        if any(path.name not in expected or not path.is_file() or path.is_symlink()
               for path in destination.iterdir()):
            raise ValueError("Export destination contains unrelated files")
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError("Destination must be empty or contain only a previous raradio export") from error
