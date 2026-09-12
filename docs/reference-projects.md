# Related Projects and raradio's Scope

English | [简体中文](reference-projects.zh-CN.md)

Checked on **2026-09-12**, using official project documentation and selected implementation and packaging files. This is a focused comparison, not an exhaustive survey. The projects were not installed or benchmarked for this review. Branch links can change; documented support below is an upstream claim, while conclusions about raradio's direction are our assessment.

[Audiblez](https://github.com/santinic/audiblez#how-to-install-the-command-line-tool) offers direct EPUB conversion through a CLI, and [ebook2audiobook](https://github.com/DrewThomasson/ebook2audiobook#basic-usage) documents headless conversion and session recovery. raradio focuses on audiobook production through commands, with straightforward installation and revision. The comparison below helps identify which workflow fits a particular task.

## Practical alternatives

| Project | Documented interface and scope | Installation boundary to consider |
| --- | --- | --- |
| [Audiblez](https://github.com/santinic/audiblez) | Direct `audiblez book.epub` CLI; optional GUI; chapter WAV and M4B output | Python package plus `espeak-ng`; `ffmpeg` for M4B. Documents CPU and CUDA execution. Its [package metadata](https://github.com/santinic/audiblez/blob/main/pyproject.toml) constrains Python to 3.10–3.12. |
| [ebook2audiobook](https://github.com/DrewThomasson/ebook2audiobook) | `--headless`, batch input and `--session` recovery alongside a web interface; many ebook/audio formats, including EPUB and M4B | Platform launchers and Docker workflows; dependencies and hardware needs vary by engine. Automatic setup can include system package managers. |
| [Abogen](https://github.com/denizsafak/abogen#interfaces) | Desktop and web interfaces; EPUB/PDF/text and subtitle workflows | `uv`/pip and platform instructions; `espeak-ng` and different GPU configurations. The [base package](https://github.com/denizsafak/abogen/blob/main/pyproject.toml) includes PyQt6 and Flask. |
| [Audiobook Creator](https://github.com/prakharsr/audiobook-creator) | Gradio workflow; LLM character attribution, multiple voices, Kokoro/Orpheus and several output formats | Configured LLM and TTS services, plus uv or Docker; FFmpeg for conversion and Calibre for the documented broader ebook/M4B workflow. |
| [Piper](https://github.com/OHF-Voice/piper1-gpl) | Local TTS engine with a [CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md), Python API and server; text/file input to audio | `piper-tts` and a separate voice download; phonemization is embedded. This is a speech component, so book organization and editorial state belong in a surrounding workflow. |

For ebook2audiobook, **multiple voices and recovery are also established product directions**. Its [E2A-SML component](https://github.com/DrewThomasson/ebook2audiobook/tree/main/components/E2A-SML) documents BookNLP dialogue attribution, a headless CLI, voice mappings and reuse of existing analysis output. The exact behavior when changing one line, accepting an uncertain speaker, or recovering after a crash still needs an execution comparison; the presence of a resume flag alone does not establish equivalent guarantees.

A command launched from a terminal can still start a UI service. In the checked Abogen [entry points](https://github.com/denizsafak/abogen/blob/main/pyproject.toml), `abogen-cli` and `abogen-web` both call the same [Flask server launcher](https://github.com/denizsafak/abogen/blob/main/abogen/webui/app.py). We therefore do not count that name alone as a batch conversion CLI. This observation does not rule out automation through its APIs or other interfaces.

For raradio, a complete headless path means that generation, status inspection, character confirmation, corrections, retries and export can all be performed without a browser or desktop control. Reading a JSON file or manually confirming a character is compatible with that goal; it still represents user effort that should be reduced where possible.

## What raradio offers today

raradio's current combination suits programmers who want to keep and revise a local audiobook project:

- **An explicit production state.** Original text, annotations, cast configuration, reference audio and segment results remain together in a working directory. Successful audio can be reused; voice changes and attribution corrections regenerate affected segments.
- **A command interface throughout.** Inspection and editing commands expose JSON, and progress uses stderr. Shell scripts can drive the same workflow as a person. See the [handbook](handbook.md) for exit codes, path semantics and cast replacement behavior.
- **Source-preserving analysis.** The analyzer annotates fixed source segments instead of returning a rewritten book. This protects text provenance; it does not guarantee that a synthesizer pronounces every word correctly.
- **A small core.** The core package has no third-party runtime dependencies, and its diagnostic workflow needs no models. Single-narrator speech skips the text LLM. Actual speech still requires the selected runtime, model weights and suitable hardware.
- **Visible extension boundaries.** Text analysis and speech synthesis are separate. The code and examples use the [MIT license](../LICENSE); dependencies and weights retain their own licenses. See the [third-party notice](../THIRD_PARTY.md).

These are useful properties to preserve, not evidence that raradio is faster, more accurate, easier to install on every machine, or more reliable than the alternatives. Those claims require comparable execution and user testing.

## Where raradio is currently limited

| Goal | Current limit |
| --- | --- |
| Simple first use | Real speech is currently an Apple Silicon/Metal workflow. A model-free diagnostic run proves the pipeline, but produces tones. It does not establish speech readiness. |
| Useful book conversion | Input is TXT; export is chapter WAV, segment-level SRT, playlist and manifest. EPUB/PDF import and MP3/M4B packaging require other tools. |
| Flexible editing | Users still edit complete cast JSON and inspect review items. A cast import replaces the full table. Source segmentation is fixed at project creation. |
| Open integration | JSON and internal Python interfaces are available, but the project is Alpha. There is no stable third-party plugin SDK, automatic plugin discovery, or broad backend selection. |
| Reliable narration | Waveform checks cannot detect misread words or measure speaker identity. Full-book quality, Chinese dialogue attribution and cross-platform speech performance need further evaluation. |

For straightforward EPUB-to-M4B conversion, Audiblez or ebook2audiobook may already cover more of the task. For visual text preparation and subtitles, Abogen is relevant. For an application that needs a speech engine rather than audiobook project management, Piper is a useful starting point. raradio is most relevant when the user wants to inspect and revise a TXT-to-audio production through commands, with the current Apple Silicon speech requirements. This is our assessment of fit, not a performance ranking.

## Lessons for the project

1. **Make the smallest useful route obvious.** Keep single-narrator speech separate from character analysis. List Python packages, external services, model downloads and hardware separately; a package manager cannot remove all four requirements. Publish one tested default installation path, with advanced choices elsewhere.
2. **Treat CLI behavior as a public interface.** Preserve predictable paths, JSON output, exit codes and useful error messages. Changes to these contracts need release notes and compatibility decisions. New UI clients should use the same underlying workflow.
3. **Spend flexibility on independent choices.** Audiobook Creator's [service configuration](https://github.com/prakharsr/audiobook-creator/blob/main/.env_sample) separates character analysis, emotion annotation and TTS endpoints. raradio can learn from that separation while keeping its own annotation contract. Similar chat APIs do not establish interchangeable schema, thinking or lifecycle behavior.
4. **Keep human corrections traceable.** Character lists, voice mappings and reusable analysis are useful across backends. BookNLP demonstrates a dedicated NLP approach; it is not evidence that either Ollama or llama.cpp is the best analysis engine for Chinese. English-oriented examples do not establish Chinese attribution quality.
5. **Measure installation and recovery as product behavior.** Check a clean environment, a short speech sample, cancellation and resume, one voice change, and one attribution correction. Record exact versions and observed limitations. Compare setup steps and manual review effort alongside audio quality and runtime before claiming an advantage.

These priorities guide further work; they do not announce new backends or completed benchmarks. See [backend strategy](backend-strategy.md) for implemented interfaces and candidates, and [verification](verification.md) for raradio's execution evidence.

## Agent-assisted use

raradio now bundles a production Skill and exposes it through `raradio agent-guide`, so users can ask an existing terminal agent to operate the review and revision workflow without a second analysis model. See the [Skill](../raradio/skills/raradio-audiobook/SKILL.md) for the current scope. The official README pages of Audiblez, ebook2audiobook and Abogen checked on 2026-09-12 did not describe a project-provided Agent Skill or MCP guide. That limited check does not rule out other repository files or third-party integrations. The useful claim is the documented end-to-end workflow, not exclusive compatibility with agents.
