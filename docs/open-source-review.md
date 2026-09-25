# Open-source readiness review

English | [简体中文](open-source-review.zh-CN.md)

Reviewed: 2026-09-12. raradio targets terminal users who want audiobook production that is easy to install, revise, and automate. This review covers the source, CLI, environment setup, documentation, and upstream tool descriptions. It is not a comparative audio-quality benchmark. Actual execution evidence is recorded in [verification](verification.md).

## Assessment

The project has a coherent Alpha scope: a dependency-free production core, explicit configuration, resumable segment state, and an optional local speech backend. It is suitable for developers willing to review casting and listen to samples on a supported Mac. It does not yet justify a promise that anyone can clone the repository and generate speech on any machine. Installation can prepare Python packages; hardware, model downloads, memory, and model capabilities remain separate requirements.

The useful distinction is the emphasis on revising a production project through a CLI. CLI conversion, multiple voices, and resume are also available elsewhere. Claims of greater simplicity, reliability, speed, or quality need a common task and measurements. See [similar projects](reference-projects.md) for concrete alternatives.

## Changes made in this review

| Area | Finding and resulting behavior |
| --- | --- |
| First run | README leads with an explicit goal and separates diagnostic tones, real speech, and character analysis. The source setup prepares Python and locked dependencies through uv. |
| Environment diagnosis | `doctor` now defaults to offline core checks. MLX and Ollama profiles report selected prerequisites, corrective hints, and a nonzero exit status when those checks fail. No inference-readiness claim is made. |
| Automation | `run.sh` preserves the caller's current directory. Invalid numeric flags are rejected before creating a project; expected corrupt-project errors are concise. Limited runs invalidate all stale completed audio before reporting remaining work, and malformed Ollama URLs produce actionable errors. |
| Versions | Project metadata and `--version` share `raradio.__version__`. A changelog and maintenance policy distinguish software versions, project schema, dependency locks, and model revisions. |
| Installation and source workflow | Setup rejects unsupported MLX hardware/macOS before dependency resolution. CI checks the locked source environment on macOS and Linux; an optional job checks MLX dependency installation. |
| Maintenance | Dependency-update PRs and a manually triggered MLX installation and dependency consistency check are configured. Model inference remains a separate validation step. |

Tests reproduce CLI failures and run the shell scripts; checking source text alone would not establish those behaviors. Hosted workflows being configured is distinct from them passing on GitHub.

## What remains, in priority order

1. **Validate the supported speech path on a fresh Mac.** Record macOS, Python and native package versions, online installation, downloads, native/GPU initialization, preset speech, and a second offline run. Test the locked versions before each speech-related public update. Current core tests do not cover native inference.
2. **Make the most common editing operations easier.** Single-voice use still needs a cast file; character edits replace the complete JSON table. A future voice preset command and targeted cast edits could remove routine JSON work. Keep full JSON import/export for reproducibility and avoid introducing a second configuration system without a concrete need.
3. **Measure the workflow advantage.** Publish an original short chapter with two characters. Measure installation steps, time to first usable audio, manual decisions, correcting one speaker, changing one voice, interruption recovery, and regenerated segments. Compare with at least one CLI alternative under stated versions. Review effort matters as much as generation speed.
4. **Expand only from demonstrated demand.** A CPU/Linux speech backend would broaden accessibility more than a UI. EPUB input and compressed chapter formats would remove common preparation steps. Each extension needs explicit capability checks and its own integration evidence; none is currently implemented.
5. **Validate the public history.** The source is prepared as one local root commit with the intended GitHub remote. After the first push, run hosted checks and keep any tagged GitHub releases tied to reviewed commits using the [maintenance procedure](maintenance.md).

## Dependency and compatibility boundaries

- Core Python support is 3.11+ on systems providing POSIX `fcntl`; macOS has local execution evidence, while Linux has configured CI coverage awaiting hosted results. Native Windows is unsupported. `--help` and `--version` being usable there does not establish project support.
- The source setup recommends Python 3.11. Current real speech is Qwen3-TTS Base/CustomVoice via the pinned MLX-Audio dependency on native Apple Silicon/macOS 14+ with Metal access. No CPU, CUDA, Intel Mac, or Linux speech backend is integrated.
- `uv.lock` fixes the resolved Python package set. It does not lock Python itself, Ollama, model weights, OS libraries, hardware, or all isolated build tools.
- The `mlx` optional dependency group is platform-gated. `setup.sh mlx` and `doctor --profile mlx` also check the actual platform so a dependency-resolution result is not mistaken for speech support.
- Models may download on first use. A small core does not imply a small complete speech installation. Cache/download access and free memory must be validated with the chosen models. Local-path or same-name model replacement is not automatically fingerprinted by its weight content.
- The project schema remains version 1. Unsupported formats are rejected; there is no general migration tool or stable Python/plugin API. Stop writers and back up the full work directory before updates that may change project state.

The project includes MIT licensing for its own material, third-party notices, contribution guidance, issue templates, original examples, and exclusion rules for generated/private files. Review tracked source before each public update. See [third-party scope](../THIRD_PARTY.md) before redistributing dependencies or model files together.
