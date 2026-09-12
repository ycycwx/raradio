# Changelog

English | [简体中文](CHANGELOG.zh-CN.md)

Only tagged releases receive version headings and dates. The application currently identifies itself as `0.1.0`; that does not imply a published Git tag or GitHub release.

## Unreleased

- Renamed the unpublished project, Python package, module, CLI, and bundled Skill from Rara to raradio.
- Standardized project metadata, GitHub links, and source-checkout installation guidance.
- Added a read-only `raradio setup` onboarding check and separate bilingual installation guides centered on the Ollama-free single-voice path.

### Manuscript ingestion and review

- Japanese chapter headings, recoverable quote diagnostics, and combining-character-safe chunk boundaries; source text and offsets remain intact.
- Semantic narration/dialogue correction, including unquoted speech, plus reviewed structure edits for chapter assignments and mixed-speaker boundaries.
- Explicit legacy text encodings, UTF-32 BOM detection, disabled heading detection, and saved import options on resume.
- Explicit reanalysis that preserves human attributions and blocks stale audio after failures or interruptions; chapter-only edits preserve existing audio and casting.
- New projects use `auto` for unspecified voice languages while legacy projects retain the Chinese default; saved confidence thresholds are honored and invalid aliases rejected.
- Bilingual guidance for unmarked manuscripts, Japanese input, and the current translation boundary.

### Initial alpha workflow

- Headless commands for importing TXT, reviewing speaker attribution and cast, synthesizing segments, resuming work, and exporting chapter WAV files.
- A standard-library core and model-free tone backend for testing the full workflow without models or optional services.
- Optional MLX Qwen3-TTS speech on Apple Silicon, with preset voices and reference-audio configurations; optional Ollama analysis.
- Bilingual guides and original examples covering narration, dialogue review, selective regeneration, and cache reuse.

### Open-source readiness

- Validate voice field types before replacing working casting; reuse verified reference recordings and publish new copies atomically, preserving existing work after interrupted imports.
- Record Ollama HTTP protocol failures for review and keep diagnostic errors structured; align the handbook with explicit encoding, structure repair, and reanalysis options.
- Bundled Agent Skill and `raradio agent-guide` (Markdown/JSON), with an agent-led CLI workflow that can use the user’s existing reasoning agent without Ollama.
- Explicit CLI-first scope, platform requirements, installation paths, and comparable-project tradeoffs.
- Correct remaining-work status for limited regeneration of missing or outdated audio; predictable caller-relative runner paths and concise invalid-configuration errors.
- A single package version source, committed dependency lock, installation preflight, and separate checks for core and optional services.
- CI configuration for locked source-checkout installs on macOS/Linux, model-free tests, and optional MLX dependency checks.
- Dependency update proposals and a documented release and project-format compatibility policy.

This remains an alpha. Automated workflow checks and short speech samples do not establish whole-book voice quality or broad hardware support. See [verification](docs/verification.md) for the recorded validation scope.
