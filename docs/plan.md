# raradio: Local Audiobook Production Plan

English | [简体中文](plan.zh-CN.md)

Goal: give terminal and automation users an audiobook production tool that is easy to install and revise. Generate audiobooks in batches after configuring characters and voices, with uncertain character attribution and generation exceptions collected for human review. The current voice backend targets Apple Silicon Macs. Source text, analysis results, voice configurations, and audio are stored independently; see [Usage Tradeoffs and Migration](usage-notes.md) for migration requirements.

## Current implementation scope

The following features are implemented in code. See [Verification](verification.md) for automated tests and short-sample runs; those records do not replace quality evaluation of whole chapters or books.

1. UTF-8 TXT import, BOM detection for UTF-16/UTF-32, and explicit source encodings such as `--encoding cp932`. Deterministic candidate chapter and speech spans preserve source offsets and carry structural issues into review; `--chapters none` disables heading detection.
2. Structured semantic and character analysis through Ollama; it can correct initial narration/dialogue kinds, including unquoted speech and quoted titles, without rewriting or repartitioning the source. Uncertain and mixed-speaker spans remain unresolved. Rules mode is an offline heuristic; single-voice mode needs no LLM and uses one reader for all text. Neither mode clears structural issues.
3. Reusable character and voice configuration; character confirmation, reference files for voice cloning, and preset voices are managed separately. New projects default unspecified voice languages to `auto`; existing projects without the new metadata retain their previous Chinese default.
4. Per-segment progress in SQLite; resume, bounded retries, individual segment regeneration, and a content-addressed audio cache. Explicit `--reanalyze` revisits automatic annotations while preserving manual attributions. The `structure` command reviews whole-source spans and applies chapter/boundary changes without editing the manuscript; unchanged spans retain their work.
5. Checks for empty audio, duration, silence, and clipping; errors and suspicious audio enter a shared exception queue.
6. Chapter WAV, SRT, and manifest export. Missing or unconfirmed segments cannot be published as complete chapters.
7. A model-free diagnostic demo, automated tests, short-sample validation records for real backends, and migration instructions.

See [Text input and structural review](text-input.md) for the input and correction workflow. Japanese source processing and language configuration are supported at these interfaces; Japanese pronunciation, character attribution, and full-book quality still require real-sample evaluation. A voice language setting does not translate the manuscript. Japanese-to-Chinese production would need a separate, reviewable target text aligned with the original spans; that translation stage is not implemented.

## Modules and interfaces

```text
TXT → script.split_text → Segment + source offsets
                            ↓
                  analysis.analyze (single-voice / rules / Ollama)
                            ↓
                 BookProject (SQLite + cast.json)
                     ↓             ↑
            backends.synthesize   Exception review
                     ↓             ↑
                  audio.inspect_wav
                     ↓
                  audio.export_chapters
```

`BookProject` centrally manages state transitions, character confirmation, cache invalidation, and recovery. Text analysis and TTS are adapted through separate modules, each providing model-free and local-model implementations. The core runtime depends only on the Python standard library; MLX is installed as needed. See [Architecture](architecture.md) for detailed data contracts.

States: `PENDING_PARSE → NEEDS_REVIEW / READY → GENERATING → DONE / FAILED / NEEDS_REVIEW`. After a process exits, the next generation run recovers segments left in `GENERATING`; only one writer is allowed per project.

Cache inputs include the source excerpt, character voice configuration, model identifier, backend version, emotion, speed, sampling settings, and reference audio content. Generated files have a recorded SHA-256 that is checked on resume. Voice configuration and annotation changes invalidate affected segments. Replacing model weights under the same identifier does not automatically change the cache key, so validation records must also capture model versions.

## Future stages

The following capabilities are not yet implemented. These stages organize the work; they do not represent committed release versions or dates.

- Stage two: ASR readback text comparisons, voice similarity checks, CLI review commands that expose audio paths for listening, and batch character confirmation.
- Stage three: EPUB import, M4B / MP3 with chapters, loudness normalization, controlled fallback voices, model installation, and capability detection.
- Stage four: character memory across chapters, annotation evaluation on real novels, and throughput optimization.

Current waveform checks cannot establish that pronunciation or character voices are correct. New ASR or voice similarity scoring should document the models, evaluation samples, and limits of false positives and false negatives. Diagnostic tones validate the pipeline and are not audiobook listening samples.

See [Backend Choices and Extension Roadmap](backend-strategy.md) for candidate text and voice backends, plugin interfaces, and evaluation requirements.

## Upstream resources

- [Ollama chat and structured output](https://docs.ollama.com/api/chat)
- [MLX-Audio](https://github.com/Blaizzy/mlx-audio)
