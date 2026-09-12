# Testing and Verification

English | [简体中文](verification.zh-CN.md)

Tests are divided into model-free workflow checks and real-model validation. Passing workflow tests establishes only the corresponding contracts; it does not establish adequate novel character recognition, word-for-word pronunciation, or cloning similarity.

## Model-free tests

Run from the source root with Python 3.11+ on a POSIX system that provides `fcntl`:

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
sh -n setup.sh run.sh
```

Tests cover source offsets and splitting, structured annotations, character confirmation, single-voice narration, cache invalidation, bounded retries, interruption recovery, a single writer, reference audio import, CLI JSON output, WAV checks, and atomic export. MLX contract tests replace model loading and inference results; installing MLX or downloading weights is unnecessary.

Public examples are also included in regression coverage: all five TXT files and seven cast templates are exercised through actual workflow checks. The offline walkthrough uses the real CLI to demonstrate manual attribution of five quoted segments across two chapters, limited runs and resume, individual segment regeneration, and selective regeneration of Xiaoyu's voice only. Tests check audio content, modification times, and output manifests to avoid mistaking regeneration for cache reuse.

```sh
python3 examples/offline_workflow.py
```

By default, the script creates a unique new directory under `work/` and keeps `book/`, `export/`, and `verification.json`. Attribution uses known answers for the original sample story; it cannot automatically identify characters in arbitrary novels, and its output is diagnostic tones only. See [Review and Voice Changes](../examples/workflow.md) for the manual steps.

The public examples can also reproduce a complete diagnostic workflow:

```sh
python3 -m raradio build examples/demo.txt --work work/verify-core \
  --analyzer rules --cast examples/cast.tone.json --output output/verify-core
python3 -m raradio build examples/story.txt --work work/verify-single \
  --analyzer single-voice --cast examples/cast.tone.json --output output/verify-single
```

The second command checks single-voice mode with dialogue in the input. Both outputs are diagnostic tones. After confirming that all export files are present, repeat the commands and verify that valid segments are not synthesized again.

## Real-model validation

Prepare the environment, models, and reference recordings using the [Handbook](handbook.md), then use short texts and templates from the [Examples Directory](../examples/README.md). Use a separate work directory for each analysis method. Validate preset voices first, followed separately by xvector, ICL, and mixed voice configurations.

When submitting reproducible validation results, record:

- raradio version or commit, Python and operating system versions, hardware model, and available memory.
- Inference library version, model repository and pinned revision, or local model file hashes; do not publish personal absolute paths.
- Original short input text, the complete configuration with personal details removed, actual commands, exit codes, and segment states.
- Generation time, audio duration, automatic check results, and specific problems heard during manual listening.
- Whether resumed runs reuse audio, whether changing a single voice regenerates only affected segments, and whether interrupted work can recover.

Do not upload reference recordings without permission to publish them; choose shareable material for a reproduction instead. Reference audio, model caches, work databases, and generated results are not distributed with the repository. All examples should be regenerated from public inputs.

## Recorded validation scope

The following summarizes development validation on 2026-09-12; it is not a release performance benchmark:

| Scope | Record |
| --- | --- |
| Automated workflow | 93 tests passed on macOS with Python 3.11 and 3.13, including public example regressions |
| Ollama + CustomVoice | Analysis of 5 segments from an original short story and synthesis with 3 preset voices; chapter WAV duration: 6.72 seconds |
| Base xvector | 1 cloned segment using synthesized narration as the reference; WAV duration: 2.96 seconds |
| Audio and resume | The samples above passed PCM16, mono, 24 kHz decoding checks; repeated runs kept valid audio unchanged |
| ICL | Parameter and adapter contract tests; no real-model quality evaluation yet |
| llama.cpp | Documentation and source research; no integration or runtime evaluation yet |

These short samples do not include a complete public evaluation dataset and cannot be used to compare performance or establish stability for long texts. Linux, whole-chapter/book quality, character attribution accuracy, ASR proofreading, voice similarity, and consistency across machines still need separate validation.

## Repository validation

The GitHub source checkout contains the CLI, documentation, tests, configuration examples, runner scripts, bundled Agent Skill, and licensing information. It excludes work databases, recordings, model weights, personal configurations, generated output, and virtual environments.

GitHub Actions is configured for model-free checks on macOS/Linux with Python 3.11–3.14 and locked core installation. A manually selected MLX job checks optional dependency installation and consistency without downloading models. These workflows were not run on GitHub's hosted infrastructure during this validation, so Linux remains unverified. Example regression tests caught mutations in temporary copies involving incorrect model types, bad reference paths, missing character mappings, and swapped voices.

## Open-source hardening checks (2026-09-12)

After the CLI and installation review, **112 tests passed on macOS with Python 3.11.15 and 3.13.14**, with `ResourceWarning` treated as an error. Shell syntax checks also passed. New regression coverage includes offline doctor profiles and failure exit codes, malformed service URLs, argument validation before project creation, corrupt project diagnostics, caller-relative runner paths with spaces, setup environment selection, and limited regeneration after cache loss or backend-version changes.

A fresh core checkout environment was created successfully; `uv lock --check --offline` succeeded with uv 0.6.5 and the CI-pinned uv 0.12.13. A separate fresh Python 3.11 environment installed the locked MLX dependencies from cached public artifacts: 56 installed packages passed `uv pip check`, and `doctor --profile mlx` passed. On this Apple Silicon Mac (macOS 26.6.2), a separate native import of `mlx.core` and `mlx_audio.tts.utils` succeeded and Metal reported available. This did not load weights, synthesize new speech, prove cold model downloads, or establish the same behavior on macOS 14 or a hosted VM.

The review also checked version consistency and diagnostic generation through the source runner. See [maintenance](maintenance.md) for the current source-update checks. The CI matrix remains configured coverage, not a claim of a hosted run; no Git release was performed in this review.

## Agent workflow checks (2026-09-12)

The Agent support update adds two CLI discovery tests. At this checkpoint the combined checkout passed **153 tests on Python 3.11.15 and 3.13.14**, including the concurrent text-workflow improvements. The bundled Skill passed its frontmatter validator and exposed identical content through Markdown, JSON, and `importlib.resources` from the source environment.

An independent agent was given only the source-prepared executable, its `agent-guide`, an original two-chapter Chinese story, and the requested outcome. Without an analyzer or model download, it configured separate narrator/character tone voices, confirmed attributions, handled a two-segment limit, completed all ten segments, and exported both chapters. Changing only Li He's tone speed to 1.2 regenerated her one dialogue segment; the other nine audio paths, hashes and modification times were retained. The input and saved source hashes remained identical. The evaluator reported no instruction blocker.

This exercise demonstrates the CLI/Skill interaction and selective repair for one small diagnostic job. It does not certify every agent client, automatic Skill discovery, long-book reasoning, actual speech or audio listening. The agent used its existing reasoning capability; raradio did not provide an Agent API or an external annotation importer. Repeat this kind of independent exercise when changing the instructions or workflow, using the [bundled Skill](../raradio/skills/raradio-audiobook/SKILL.md).

## Final initial-commit review (2026-09-12)

Independent review of project state, adapters, packaging, and bilingual documentation found three issues: HTTP protocol failures bypassed Ollama error handling, invalid voice field types could replace working casting, and interrupted reference reimports could damage an existing copy. Regression tests reproduced the failures before the fixes. The fixes normalize transport errors, validate casting before mutation, and reuse verified recordings or publish complete copies after hash verification. Follow-up review found no remaining blockers in those changes.

The resulting checkout passed **160 model-free tests on Python 3.11.15 and 3.13.14** on macOS, with `ResourceWarning` treated as an error. Shell syntax and the offline lockfile check passed. The handbook now matches the explicit encoding, structure-repair, and reanalysis commands in both languages. This review adds no real-model inference or listening-quality claim.
