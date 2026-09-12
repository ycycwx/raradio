# raradio Architecture and Data Contracts

English | [简体中文](architecture.zh-CN.md)

raradio uses character voice configurations for resumable batch processing: the source text stays fixed, a model supplies annotations, a voice backend synthesizes audio, and a human handles exceptions in one place. The current entry point is a local CLI with TXT input, and the core workflow depends only on the Python standard library. This document describes the existing implementation; unimplemented capabilities are listed at the end. See [Verification](verification.md) for the scope of runtime validation.

## Module boundaries

| Module | Input → output | Constraints it owns |
| --- | --- | --- |
| `script.py` | Source text → list of `Segment` objects | Deterministic candidate chapters and speech spans; preserves source offsets and records structural issues for review |
| `structure.py` | Reviewed source spans → validated segments | Allows explicit chapter and boundary corrections while rejecting stale edits, overlap, omitted text, and source rewrites |
| `models.py` | `Segment`, `Character`, `VoiceProfile`, `AnalysisResult` | Represents text segments, character identities, and voice configurations separately; characters are independent of any TTS implementation |
| `analysis.py` | Segments + known characters → semantic kind, character, emotion, and confidence annotations | Single-voice mode assigns everything to the narrator; rules mode trusts the parser's heuristic; Ollama can correct semantic kinds but cannot rewrite or repartition the source; invalid annotations are rejected |
| `project.py` | Import, annotation, voice configuration, and review operations → persistent project state | Exclusive writes, state transitions, cache invalidation, bounded retries, resume, and integrity checks |
| `backends.py` | `synthesize(text, voice, emotion, output)` → PCM16 WAV file | Adapts to actual model capabilities; rejects unsupported parameters explicitly; supplies a backend version identifier |
| `audio.py` | WAV + source text → measurements; completed segments → chapter files | Structural validation, waveform warnings, sample-based concatenation, SRT, provenance manifests, and export rollback |

A `Segment`'s `id/chapter/chapter_title/index/start/end/text` fields identify its source slice; `kind/speaker_id/confidence/emotion/reason` describe its annotations. Offsets are character positions in the decoded text, with a read range of `[start:end]`. The parser's initial `kind` is a hint: quoted text can be a title or quotation, and unquoted text can contain dialogue. Ollama may correct `kind` to `narration` or `dialogue`; narration must use the narrator. It must leave uncertain or mixed-speaker spans unresolved instead of assigning one character to the whole span. Source fields and `parse_issues` cannot change during analysis.

Structural corrections use `raradio structure WORK` to export a review document and `raradio structure WORK --file reviewed.json` to apply it. The document describes the whole source as ordered spans and chapter assignments. This explicit operation can revise boundaries and chapters without editing `source.txt`. Unchanged spans and chapter/title-only edits retain annotations, human decisions, and audio. Boundary or kind changes return for analysis; unresolved parse findings remain subject to review. `resolve` changes one segment's speaker or emotion, not its boundaries. See [Text input and structural review](text-input.md).

These are internal module boundaries. No stable third-party plugin interface has been released. Analyzers and TTS backends are selected from built-in lists; configuration files do not automatically discover external implementations.

Ollama analyzes batches with neighboring context and the accumulated character list; the project saves results by chapter. Character confirmations and manual corrections to individual segments persist independently, and later analysis preserves manually corrected segments. A complete system for remembering plot context across chapters is not yet implemented.

`single-voice` is an explicit choice to have one reader speak all text: it does not call an LLM, preserves the source structure of every segment, and annotates everything as `narrator / neutral`. It does not infer emotions or character attribution. `rules` is an offline heuristic and cannot identify unquoted speech or distinguish quoted titles from dialogue. By default, analysis processes only segments that have neither been successfully analyzed nor manually corrected. Use `analyze WORK --reanalyze` to revisit automatic annotations; manually corrected attributions remain preserved. Neither mode clears structural issues.

Import defaults to UTF-8, with BOM detection for UTF-16 and UTF-32; other encodings require an explicit value such as `--encoding cp932`. `--chapters none` disables heading detection. New projects default unspecified voice languages to `auto`, and configuration persists that value; older projects without this metadata retain the previous Chinese default. A selected TTS model must support the requested language. These controls do not translate Japanese into Chinese or normalize ruby and editorial notes into a separate reading text.

## Project directory

```text
book-project/
├── source.txt       # Fixed source text decoded to UTF-8
├── project.json     # Data version, title, source SHA-256, encoding, splitting parameters, default language
├── cast.json        # Characters, aliases, confirmation status, and voice configurations
├── state.sqlite3    # Per-segment annotations, state, attempts, cache fingerprints, audio hashes, QA
├── voices/          # Reference audio copied during configuration, named by content hash
├── audio/           # Generated WAV files per segment; temporary files during generation
└── .write.lock      # Write lock for this project
```

In `cast.json`, each entry in `characters` uses `voice` to reference a configuration in `voices`. The narrator has the fixed character ID `narrator`. Once the main characters have been confirmed, segments with sufficient confidence, available voices, and no unresolved structural issues enter the generation queue automatically. New characters, uncertain attribution, missing voices, or `parse_issues` require further attention.

Do not edit `state.sqlite3` directly or replace `source.txt`. Opening a project checks the source SHA-256; import a revised text into a new project. Replacing reference audio through the configuration entry point copies the file into the project, so runtime operation no longer depends on its original location.

Project mutations use POSIX `fcntl` to acquire an exclusive lock through `.write.lock`; concurrent writes to the same project are rejected. Native Windows write locking is not yet implemented. To migrate, stop writes and copy the complete project directory. See [Usage Tradeoffs and Migration](usage-notes.md).

## States and human intervention

```text
PENDING_PARSE ──analyze──→ READY ──generate──→ GENERATING ──checks pass──→ DONE
                       ↘ NEEDS_REVIEW                  ├─suspect audio──→ NEEDS_REVIEW
                                                       └─retries exhausted──→ FAILED
```

| State | Meaning and next step |
| --- | --- |
| `PENDING_PARSE` | Annotation is incomplete; run analysis |
| `NEEDS_REVIEW` | Structural issues remain, analysis failed, attribution confidence is low, a character is unconfirmed, a voice configuration is missing, or audio warnings remain after repeated generation; address the `issue` |
| `READY` | Annotations and character-to-voice mappings are usable; waiting for generation |
| `GENERATING` | The current attempt has been saved; the next generation run recovers scheduling after an interruption |
| `DONE` | Waveform checks passed, or a human accepted the current audio warnings |
| `FAILED` | The bounded retries for this run failed; fix the cause, then retry the affected segment |

Each segment gets up to 3 attempts by default, including regeneration of suspicious audio. Automatic retries happen before the segment enters the human review queue. Rerunning does not retry segments awaiting review or failed segments indefinitely. Correcting character attribution, regenerating an individual segment, and accepting audio after listening are separate operations. Accepting audio does not confirm a character and cannot accept a missing or modified file.

## Caching and export

The input cache key includes the source excerpt, character, emotion, and complete voice configuration; when reference audio is present, it also includes that file's SHA-256. The generation fingerprint adds the backend version. Changes to an effective configuration return affected segments to `READY`; missing configurations or unconfirmed characters put them in `NEEDS_REVIEW`. When multiple characters share one voice configuration, a change affects all segments using it. Regeneration clears previous manual audio acceptance; generation recovery validates both the fingerprint and the actual audio SHA-256.

Model identifiers are part of the cache key, but replacing model weights in place under the same path does not change the identifier. To preserve reproducibility, record the model version or keep a fixed local model directory. After upgrading dependencies or models, run a generation check before exporting.

Export requires all segments to be `DONE` and checks the current configuration, backend version, and audio integrity. Damaged WAV structures or inconsistent sample formats cause export to fail; manually accepted quality warnings remain in the manifest. Chapter filenames use sequence numbers rather than chapter titles.

```text
export-directory/
├── chapter-0001.wav
├── chapter-0001.srt
├── …
├── manifest.json    # Source segments, input audio SHA-256, QA, sample counts, start/end times
└── playlist.m3u
```

All chapters are first written to a sibling temporary directory, then published when complete. If publication fails, the exporter attempts to restore the old directory. Updating an export removes surplus chapters from the previous manifest but refuses to overwrite a directory containing other files. SRT timing comes from cumulative sample counts and pauses between segments, not text-based estimates. Subtitles are aligned to segments, not individual words.

## Future stages

The following capabilities are not yet implemented. See the [Implementation Plan](plan.md) for their order.

1. **Reduce listening review work:** ASR readback comparisons, voice similarity checks, an exception queue with audio playback, and batch character review. New checks must be validated with real models and samples.
2. **Expand input and delivery:** EPUB, M4B/MP3 with chapters, loudness processing, explicitly configurable fallback voices, and model capability detection.
3. **Evaluate and optimize long tasks:** character memory across chapters, novel annotation benchmarks, and throughput and memory optimization.

A complete graphical interface, ASR, and speaker identity verification are outside the capabilities of the current waveform QA. Future modules should reuse existing segment and project data while preserving the immutable-source constraint.

Japanese input and semantic correction support do not establish Japanese attribution or pronunciation quality. Translation is a separate future concern: it would require a reviewable target text linked to the original spans, rather than rewriting source text inside the analyzer or relying on a TTS language setting.

See [Backend Choices and Extension Roadmap](backend-strategy.md) for llama.cpp candidates, current interfaces, and the capabilities still needed for third-party plugins.
