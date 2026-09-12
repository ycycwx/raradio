"""Durable workflow: source, annotations, casting and audio have separate lifecycles."""

from __future__ import annotations

import hashlib
import codecs
import json
import math
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from dataclasses import asdict, replace
from pathlib import Path

from .models import Character, Segment, VoiceProfile

try:
    import fcntl
except ImportError:
    fcntl = None


def _require_file_locking():
    if fcntl is None:
        raise RuntimeError("raradio projects require POSIX fcntl file locking; use macOS or Linux. Native Windows is not supported.")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(_json(value) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _copy_reference(source, destination, digest):
    """Reuse verified media; publish a new copy only after its hash matches."""
    if destination.is_file() and _digest(destination) == digest:
        return
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".reference-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copyfile(source, temporary)
        if _digest(temporary) != digest:
            raise ValueError(f"Reference audio changed during import: {source}; retry with a stable recording")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def read_source(source, encoding=None):
    """Decode explicitly or use BOM/UTF-8; never guess a legacy encoding."""
    raw = Path(source).read_bytes()
    if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        detected = "utf-32"
    elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        detected = "utf-16"
    else:
        detected = "utf-8-sig"
    selected = encoding or detected
    try:
        codecs.lookup(selected)
        return raw.decode(selected)
    except LookupError as exc:
        raise ValueError(f"Unknown source encoding: {selected}") from exc
    except UnicodeError as exc:
        raise ValueError(f"Cannot decode source as {selected}; pass --encoding with the file's actual encoding (for example cp932)") from exc


class BookProject:
    def __init__(self, root):
        _require_file_locking()
        self.root = Path(root).resolve()
        if not (self.root / "state.sqlite3").is_file():
            raise FileNotFoundError(f"Not a raradio project: {self.root}")
        metadata = json.loads((self.root / "project.json").read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("Invalid project metadata: project.json must contain an object")
        if type(metadata.get("schema_version")) is not int or metadata["schema_version"] != 1:
            raise ValueError("Unsupported project schema version")
        if not isinstance(metadata.get("source_sha256"), str):
            raise ValueError("Invalid project metadata: source_sha256 is required")
        if _digest(self.root / "source.txt") != metadata["source_sha256"]:
            raise ValueError("Source text has changed; import it into a new project")
        threshold = metadata.get("confidence_threshold", 0.8)
        if type(threshold) not in (int, float) or not 0 <= threshold <= 1:
            raise ValueError("Invalid project confidence_threshold; expected a number between 0 and 1")
        self.metadata = metadata

    @classmethod
    def create(cls, source, root, max_chars=240, *, encoding=None, chapter_mode="auto"):
        from .script import split_text

        _require_file_locking()
        source = Path(source)
        text = read_source(source, encoding)
        segments = split_text(text, max_chars=max_chars, chapter_mode=chapter_mode)
        if not segments:
            raise ValueError("The source contains no readable text")
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=False)
        (root / "audio").mkdir()
        (root / "voices").mkdir()
        (root / "source.txt").write_text(text, encoding="utf-8", newline="")
        _atomic_json(root / "project.json", {
            "schema_version": 1, "title": source.stem, "source_sha256": _digest(root / "source.txt"),
            "max_chars": max_chars, "confidence_threshold": 0.8,
            "encoding": encoding, "chapter_mode": chapter_mode, "default_language": "auto",
        })
        _atomic_json(root / "cast.json", {
            "characters": {"narrator": {"name": "Narrator", "aliases": [], "voice": None, "confirmed": False}},
            "voices": {},
        })
        with closing(sqlite3.connect(root / "state.sqlite3")) as db, db:
            db.execute("""CREATE TABLE segments (
                id TEXT PRIMARY KEY, position INTEGER UNIQUE NOT NULL, payload TEXT NOT NULL,
                status TEXT NOT NULL, analyzed INTEGER DEFAULT 0, reviewed INTEGER DEFAULT 0,
                input_key TEXT, fingerprint TEXT, audio_path TEXT, audio_sha TEXT,
                attempts INTEGER DEFAULT 0, issue TEXT DEFAULT '', qa TEXT DEFAULT '{}',
                accepted INTEGER DEFAULT 0)""")
            db.executemany("INSERT INTO segments(id,position,payload,status,issue) VALUES(?,?,?,?,?)",
                           [(s.id, i, _json(asdict(s)), "NEEDS_REVIEW" if s.parse_issues else "PENDING_PARSE",
                             "parse: " + "; ".join(s.parse_issues) if s.parse_issues else "")
                            for i, s in enumerate(segments)])
        return cls(root)

    @contextmanager
    def _write(self):
        with (self.root / ".write.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("This project is already being modified by another process") from exc
            try:
                with closing(sqlite3.connect(self.root / "state.sqlite3")) as db:
                    db.row_factory = sqlite3.Row
                    yield db
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def casting(self):
        return json.loads((self.root / "cast.json").read_text(encoding="utf-8"))

    def segments(self):
        with closing(sqlite3.connect(self.root / "state.sqlite3")) as db:
            db.row_factory = sqlite3.Row
            result = []
            for row in db.execute("SELECT * FROM segments ORDER BY position"):
                item = json.loads(row["payload"])
                item.update({key: row[key] for key in ("status", "attempts", "issue", "audio_path", "audio_sha", "accepted")})
                item["qa"] = json.loads(row["qa"])
                result.append(item)
            return result

    def status(self):
        counts = {}
        for item in self.segments():
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return {"project": str(self.root), "counts": counts, "total": sum(counts.values()),
                "remaining": sum(v for k, v in counts.items() if k != "DONE")}

    def review(self):
        return [item for item in self.segments() if item["status"] in ("NEEDS_REVIEW", "FAILED")]

    def structure(self):
        from .structure import structure_document

        return structure_document(self.metadata["source_sha256"], self.segments())

    def restructure(self, document):
        """Apply reviewed spans atomically, retaining unchanged annotations/audio."""
        from .structure import structure_document, validate_structure

        with self._write() as db:
            with (self.root / "source.txt").open(encoding="utf-8", newline="") as stream:
                text = stream.read()
            rows = [dict(row) for row in db.execute("SELECT * FROM segments ORDER BY position")]
            original = {row["id"]: row for row in rows}
            payloads = [json.loads(row["payload"]) for row in rows]
            issues = [payload for payload in payloads if payload.get("parse_issues")]
            current = structure_document(self.metadata["source_sha256"], payloads)
            segments = validate_structure(document, current, text, self.metadata["max_chars"])
            records = []
            issue_cursor = 0
            for segment in segments:
                previous = original.get(segment.id)
                before = json.loads(previous["payload"]) if previous else {}
                unchanged = previous and all(before[k] == getattr(segment, k) for k in
                                             ("start", "end", "text", "kind"))
                if unchanged:
                    before.update(index=segment.index, chapter=segment.chapter, chapter_title=segment.chapter_title)
                    record = dict(previous, position=segment.index, payload=_json(before))
                else:
                    # Boundary/title edits do not acknowledge unrelated parse
                    # findings. Explicit speaker review remains the gate.
                    while issue_cursor < len(issues) and issues[issue_cursor]["end"] <= segment.start:
                        issue_cursor += 1
                    inherited_issues = []
                    probe = issue_cursor
                    while probe < len(issues) and issues[probe]["start"] < segment.end:
                        inherited_issues.extend(issues[probe]["parse_issues"])
                        probe += 1
                    inherited = tuple(dict.fromkeys(inherited_issues))
                    segment = replace(segment, parse_issues=inherited)
                    record = {"id": segment.id, "position": segment.index, "payload": _json(asdict(segment)),
                              "status": "NEEDS_REVIEW" if inherited else "PENDING_PARSE", "analyzed": 0, "reviewed": 0,
                              "input_key": None, "fingerprint": None, "audio_path": None, "audio_sha": None,
                              "attempts": 0, "issue": "parse: " + "; ".join(inherited) if inherited else "",
                              "qa": "{}", "accepted": 0}
                records.append(record)
            with db:
                db.execute("DELETE FROM segments")
                fields = list(records[0])
                db.executemany(f"INSERT INTO segments({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
                               [[record[field] for field in fields] for record in records])
        return self.status()

    def _voice(self, segment, cast):
        character = cast["characters"].get(segment.speaker_id)
        if not character or not character.get("confirmed"):
            raise ValueError("speaker: confirm the character and assign a voice")
        profile_id = character.get("voice")
        if profile_id not in cast["voices"]:
            raise ValueError("speaker: voice profile is missing")
        data = dict(cast["voices"][profile_id])
        data.setdefault("language", self.metadata.get("default_language", "Chinese"))
        return VoiceProfile(id=profile_id, **data)

    def _input_key(self, segment, profile, reference_digests=None):
        profile_data = asdict(profile)
        if profile.reference_audio:
            reference_digests = {} if reference_digests is None else reference_digests
            if profile.reference_audio not in reference_digests:
                reference_digests[profile.reference_audio] = _digest(self.root / profile.reference_audio)
            profile_data["reference_sha256"] = reference_digests[profile.reference_audio]
        return hashlib.sha256(_json({"text": segment.text, "speaker": segment.speaker_id,
                                    "emotion": segment.emotion, "voice": profile_data}).encode()).hexdigest()

    def _refresh(self, db, cast):
        reference_digests = {}
        for row in list(db.execute("SELECT * FROM segments ORDER BY position")):
            segment = Segment(**json.loads(row["payload"]))
            if not row["analyzed"]:
                continue
            try:
                if segment.parse_issues and not row["reviewed"]:
                    raise ValueError("parse: " + "; ".join(segment.parse_issues) + "; inspect structure or resolve the segment")
                if not segment.speaker_id or segment.confidence < self.metadata.get("confidence_threshold", 0.8):
                    raise ValueError("speaker: uncertain attribution; resolve this segment")
                profile = self._voice(segment, cast)
                key = self._input_key(segment, profile, reference_digests)
            except (ValueError, OSError) as exc:
                db.execute("UPDATE segments SET status='NEEDS_REVIEW', issue=? WHERE id=?", (str(exc), row["id"]))
                continue
            if key != row["input_key"]:
                db.execute("""UPDATE segments SET status='READY', input_key=?, fingerprint=NULL,
                    audio_path=NULL,audio_sha=NULL,attempts=0,issue='',qa='{}',accepted=0 WHERE id=?""", (key, row["id"]))
            elif row["status"] == "NEEDS_REVIEW" and not row["issue"].startswith("audio:"):
                if self._valid_audio(row):
                    issues = json.loads(row["qa"]).get("issues", [])
                    if issues and not row["accepted"]:
                        db.execute("UPDATE segments SET issue=? WHERE id=?", ("audio: " + ", ".join(issues), row["id"]))
                    else:
                        db.execute("UPDATE segments SET status='DONE', issue='' WHERE id=?", (row["id"],))
                else:
                    db.execute("UPDATE segments SET status='READY', attempts=0, issue='' WHERE id=?", (row["id"],))
        db.commit()

    def configure(self, cast, base_dir=None):
        """Replace the reviewed cast; copy reference media into the portable project."""
        cast = json.loads(_json(cast))
        if not isinstance(cast, dict) or not isinstance(cast.get("characters"), dict) or not isinstance(cast.get("voices"), dict):
            raise ValueError("Cast requires characters and voices objects")
        base_dir = Path(base_dir or self.root).resolve()
        references = []
        for voice_id, data in cast["voices"].items():
            if not isinstance(data, dict):
                raise ValueError(f"Invalid voice {voice_id}: expected an object")
            data.setdefault("language", self.metadata.get("default_language", "Chinese"))
            if not isinstance(data["language"], str) or not data["language"].strip():
                raise ValueError(f"Invalid voice {voice_id}: language must be nonempty")
            try:
                profile = VoiceProfile(id=voice_id, **data)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid voice {voice_id}: {exc}") from exc
            for field in ("model", "instruct", "clone_mode", "emotion_mode"):
                if not isinstance(getattr(profile, field), str):
                    raise ValueError(f"Invalid voice {voice_id}: {field} must be a string")
            for field in ("reference_audio", "reference_text", "speaker"):
                value = getattr(profile, field)
                if value is not None and not isinstance(value, str):
                    raise ValueError(f"Invalid voice {voice_id}: {field} must be a string or null")
            if profile.backend not in ("tone", "mlx"):
                raise ValueError(f"Unknown backend: {profile.backend}")
            if type(profile.seed) is not int:
                raise ValueError(f"Invalid voice {voice_id}: seed must be an integer")
            if type(profile.speed) not in (int, float) or not 0 < profile.speed < math.inf:
                raise ValueError("Voice speed must be positive and finite")
            if type(profile.temperature) not in (int, float) or not 0 <= profile.temperature < math.inf:
                raise ValueError("Voice temperature must be nonnegative and finite")
            if profile.reference_audio:
                path = (base_dir / profile.reference_audio).resolve()
                if not path.is_file():
                    raise ValueError(f"Reference audio does not exist: {path}")
                digest = _digest(path)
                relative = "voices/" + digest + path.suffix.lower()
                data["reference_audio"] = relative
                references.append((path, self.root / relative, digest))
        for char_id, character in cast["characters"].items():
            if not isinstance(character, dict) or not isinstance(character.get("name"), str):
                raise ValueError(f"Invalid character: {char_id}")
            if type(character.get("confirmed", False)) is not bool:
                raise ValueError("Character confirmed must be a boolean")
            if character.get("confirmed") and character.get("voice") not in cast["voices"]:
                raise ValueError(f"Confirmed character {char_id} needs an existing voice")
            aliases = character.get("aliases", [])
            if not isinstance(aliases, list) or any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
                raise ValueError("Character aliases must be a list of nonempty strings")
        with self._write() as db:
            for source, destination, digest in references:
                _copy_reference(source, destination, digest)
            _atomic_json(self.root / "cast.json", cast)
            self._refresh(db, cast)

    def analyze(self, analyzer, *, reanalyze=False):
        """Commit analysis chapter by chapter, preserving all confirmed corrections."""
        with self._write() as db:
            cast = self.casting()
            rows = list(db.execute("SELECT * FROM segments WHERE reviewed=0 AND (analyzed=0 OR ?) ORDER BY position",
                                   (bool(reanalyze),)))
            if reanalyze:
                # Commit the intent before model work: a crash/interruption
                # must not leave old annotations/audio claiming completion.
                with db:
                    db.executemany("UPDATE segments SET analyzed=0,status='NEEDS_REVIEW',issue='analysis: reanalysis pending' WHERE id=?",
                                   [(row["id"],) for row in rows])
            chapters = {}
            for row in rows:
                segment = Segment(**json.loads(row["payload"]))
                chapters.setdefault(segment.chapter, []).append(segment)
            for segments in chapters.values():
                characters = [Character(id=key, name=value["name"], aliases=tuple(value.get("aliases", [])))
                              for key, value in cast["characters"].items()]
                try:
                    result = analyzer.analyze(segments, characters)
                    original = {s.id: s for s in segments}
                    if len(result.segments) != len(segments) or {s.id for s in result.segments} != set(original):
                        raise ValueError("Analysis must cover every original segment exactly once")
                    for segment in result.segments:
                        before = original[segment.id]
                        if any(getattr(segment, key) != getattr(before, key) for key in
                               ("text", "start", "end", "index", "chapter", "chapter_title")) or tuple(segment.parse_issues) != tuple(before.parse_issues):
                            raise ValueError("Analysis tried to change source text or structure")
                        if segment.kind not in ("narration", "dialogue"):
                            raise ValueError("Invalid analysis kind")
                        if type(segment.confidence) not in (int, float) or not 0 <= segment.confidence <= 1:
                            raise ValueError("Invalid analysis confidence")
                    for character in result.characters:
                        existing = cast["characters"].get(character.id)
                        if existing and existing["name"] != character.name:
                            raise ValueError(f"Conflicting name for character {character.id}")
                    for character in result.characters:
                        if character.id in cast["characters"]:
                            existing = cast["characters"][character.id]
                            existing["aliases"] = list(dict.fromkeys([*existing.get("aliases", []), *character.aliases]))
                        else:
                            cast["characters"][character.id] = {"name": character.name, "aliases": list(character.aliases),
                                                               "voice": None, "confirmed": False}
                    _atomic_json(self.root / "cast.json", cast)
                    with db:
                        for segment in result.segments:
                            db.execute("UPDATE segments SET payload=?,analyzed=1,status='NEEDS_REVIEW',issue='' WHERE id=?",
                                       (_json(asdict(segment)), segment.id))
                except (ValueError, RuntimeError, OSError) as exc:
                    with db:
                        db.executemany("UPDATE segments SET analyzed=0,status='NEEDS_REVIEW',issue=? WHERE id=?",
                                       [("analysis: " + str(exc), segment.id) for segment in segments])
            self._refresh(db, cast)
        return self.status()

    def resolve(self, segment_id, speaker_id, emotion=None):
        with self._write() as db:
            row = db.execute("SELECT * FROM segments WHERE id=?", (segment_id,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown segment: {segment_id}")
            payload = json.loads(row["payload"])
            payload.update(speaker_id=speaker_id, confidence=1.0, reason="Explicit attribution")
            if emotion is not None:
                payload["emotion"] = emotion
            self._voice(Segment(**payload), self.casting())
            with db:
                db.execute("""UPDATE segments SET payload=?, reviewed=1, analyzed=1,
                    status='READY',input_key=NULL,qa='{}',accepted=0,issue='' WHERE id=?""", (_json(payload), segment_id))
            self._refresh(db, self.casting())

    def retry(self, segment_id):
        with self._write() as db, db:
            row = db.execute("SELECT * FROM segments WHERE id=?", (segment_id,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown segment: {segment_id}")
            db.execute("""UPDATE segments SET status=?,attempts=0,fingerprint=NULL,
                audio_path=NULL,audio_sha=NULL,qa='{}',accepted=0,issue='' WHERE id=?""",
                       ("READY" if row["analyzed"] else "PENDING_PARSE", segment_id))
            self._refresh(db, self.casting())

    def accept_audio(self, segment_id):
        with self._write() as db:
            self._refresh(db, self.casting())
            row = db.execute("SELECT * FROM segments WHERE id=?", (segment_id,)).fetchone()
            if row is None or row["status"] != "NEEDS_REVIEW" or not row["issue"].startswith("audio:"):
                raise ValueError("Only a current audio QA finding can be accepted")
            if not self._valid_audio(row):
                raise ValueError("Audio is missing or changed; retry generation")
            with db:
                db.execute("UPDATE segments SET status='DONE',accepted=1,issue='' WHERE id=?", (segment_id,))

    def _valid_audio(self, row):
        if not row["audio_path"] or not row["audio_sha"]:
            return False
        try:
            return _digest(self.root / row["audio_path"]) == row["audio_sha"]
        except OSError:
            return False

    def run(self, backends=None, limit=None, max_attempts=3, on_event=None):
        from .audio import inspect_wav
        from .backends import get_backend

        if max_attempts < 1 or (limit is not None and limit < 1):
            raise ValueError("limit and max_attempts must be positive")
        instances = dict(backends or {})
        processed = 0
        with self._write() as db:
            cast = self.casting()
            self._refresh(db, cast)
            with db:
                db.execute("UPDATE segments SET status='READY',attempts=MAX(0,attempts-1) WHERE status='GENERATING'")
                # A generation limit must not leave stale caches claiming DONE.
                # Validate every completed segment before attempting any new audio.
                for row in list(db.execute("SELECT * FROM segments WHERE status='DONE' ORDER BY position")):
                    profile = self._voice(Segment(**json.loads(row["payload"])), cast)
                    if profile.backend not in instances:
                        instances[profile.backend] = get_backend(profile.backend)
                    fingerprint = hashlib.sha256((row["input_key"] + instances[profile.backend].version).encode()).hexdigest()
                    if row["fingerprint"] != fingerprint or not self._valid_audio(row):
                        db.execute("""UPDATE segments SET status='READY',fingerprint=NULL,
                            audio_path=NULL,audio_sha=NULL,attempts=0,issue='',qa='{}',accepted=0 WHERE id=?""", (row["id"],))
            for row in list(db.execute("SELECT * FROM segments WHERE status='READY' ORDER BY position")):
                if limit is not None and processed >= limit:
                    break
                segment = Segment(**json.loads(row["payload"]))
                profile = self._voice(segment, cast)
                if profile.backend not in instances:
                    instances[profile.backend] = get_backend(profile.backend)
                backend = instances[profile.backend]
                fingerprint = hashlib.sha256((row["input_key"] + backend.version).encode()).hexdigest()
                processed += 1
                attempts = row["attempts"] if row["fingerprint"] == fingerprint else 0
                if profile.reference_audio:
                    data = asdict(profile)
                    data["reference_audio"] = str(self.root / profile.reference_audio)
                    profile = VoiceProfile(**data)
                while attempts < max_attempts:
                    attempts += 1
                    with db:
                        db.execute("""UPDATE segments SET status='GENERATING',attempts=?,fingerprint=?,
                            audio_path=NULL,audio_sha=NULL,qa='{}',accepted=0 WHERE id=?""",
                                   (attempts, fingerprint, row["id"]))
                    fd, temporary = tempfile.mkstemp(suffix=".wav", prefix=".generating-", dir=self.root / "audio")
                    os.close(fd)
                    try:
                        attempt_profile = replace(profile, seed=profile.seed + attempts - 1)
                        if on_event:
                            on_event({"segment": segment.id, "attempt": attempts, "speaker": segment.speaker_id})
                        backend.synthesize(segment.text, attempt_profile, segment.emotion, Path(temporary))
                        qa = inspect_wav(Path(temporary), segment.text)
                        qa["generation"] = {"backend": profile.backend, "backend_version": backend.version,
                                            "model": profile.model, "voice_id": profile.id, "seed": attempt_profile.seed,
                                            "emotion_mode": profile.emotion_mode}
                        if qa["issues"] and attempts < max_attempts:
                            continue
                        audio_sha = _digest(temporary)
                        relative = "audio/" + fingerprint + "-" + audio_sha[:16] + ".wav"
                        destination = self.root / relative
                        os.replace(temporary, destination)
                        with db:
                            db.execute("""UPDATE segments SET status=?,audio_path=?,audio_sha=?,qa=?,issue=?,accepted=0 WHERE id=?""",
                                       ("NEEDS_REVIEW" if qa["issues"] else "DONE", relative, audio_sha, _json(qa),
                                        "audio: " + ", ".join(qa["issues"]) if qa["issues"] else "", row["id"]))
                        break
                    except Exception as exc:
                        with db:
                            db.execute("UPDATE segments SET status='FAILED',issue=? WHERE id=?", (f"generation: {type(exc).__name__}: {exc}", row["id"]))
                    finally:
                        Path(temporary).unlink(missing_ok=True)
                else:
                    with db:
                        db.execute("UPDATE segments SET status='FAILED' WHERE id=?", (row["id"],))
        return self.status()

    def export(self, destination, pause_ms=180, backends=None):
        from .audio import export_chapters
        from .backends import get_backend

        with self._write() as db:
            cast = self.casting()
            instances = dict(backends or {})
            self._refresh(db, cast)
            for row in db.execute("SELECT * FROM segments"):
                if row["status"] != "DONE" or not self._valid_audio(row):
                    raise ValueError(f"Cannot export: segment {row['id']} is incomplete or audio changed")
                profile = self._voice(Segment(**json.loads(row["payload"])), cast)
                if profile.backend not in instances:
                    instances[profile.backend] = get_backend(profile.backend)
                fingerprint = hashlib.sha256((row["input_key"] + instances[profile.backend].version).encode()).hexdigest()
                if row["fingerprint"] != fingerprint:
                    raise ValueError(f"Cannot export: backend changed for {row['id']}; run generation to refresh")
            return export_chapters(self.segments(), self.root, Path(destination), pause_ms=pause_ms)
