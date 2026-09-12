# Backend Choices and Extension Roadmap

English | [简体中文](backend-strategy.zh-CN.md)

Upstream documentation checked on: 2026-09-12. This document distinguishes implemented raradio backends from candidates. See the [Handbook](handbook.md) for installation and commands, and [Verification](verification.md) for runtime evidence and limitations.

See [Related Project Research](reference-projects.md) for CLI alternatives, their workflow choices, and useful lessons. It distinguishes general-purpose APIs, Ollama adapters, rules, and BookNLP character analysis as references for future interface design.

## Current backends

raradio currently provides Ollama text analysis and MLX speech synthesis. llama.cpp is a candidate extension to evaluate and has not been integrated. Text analysis and speech generation need separate evaluation before changing default backends. Single-voice narration can skip the text LLM entirely.

Backend choices should be based on runtime results for specific interfaces, models, and versions. Community size and hardware coverage can help shortlist candidates, but they do not establish raradio's voice quality, generation speed, or reliability over long tasks.

raradio has two distinct tasks whose engines can be replaced independently:

```text
Source TXT → Chapters and segments → Character/emotion annotations → Confirmed characters and voices → Segment audio → QA → Chapter export
                                              ↑                                                           ↑
                                Text analyzer; LLM optional                                           TTS backend
                                Current: Ollama / rules /                                             Current: MLX / tone
                                         single-voice                                                 (tone is diagnostic only)
                                Candidate: llama-server                                               Candidate: llama-tts
```

Text analysis and speech synthesis use different model interfaces. The speech step needs a TTS model supported by the backend and its audio processing components; a text model cannot directly replace them.

## Routes and status

| Route | Implications for community, installation, and customization | Current raradio status |
| --- | --- | --- |
| Ollama text analysis + MLX TTS | Ollama manages text models; MLX-Audio's Python API synthesizes speech; the current voice path targets Apple Silicon Macs | Implemented; see [Verification](verification.md) for short-sample runtime evidence; no quality conclusions for whole books yet |
| llama-server text analysis + MLX TTS | Users familiar with llama.cpp can reuse their own service and inference parameters while keeping the voice workflow | Text adapter not yet implemented |
| llama-server text analysis + llama-tts speech | Evaluate speech generation on other devices; requires wrappers for the speech process, audio contract, and installation | Not integrated into raradio; upstream provides a speech generation demo tool |

`llama-server` provides an OpenAI-compatible chat interface and schema-constrained JSON output. See the [llama-server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). raradio's Ollama analyzer uses `/api/chat` and its `format`, `think`, and `keep_alive` parameters, so other protocols need a separate adapter; changing only `--ollama-url` is insufficient. Speech synthesis also needs its own adapter: chat interface compatibility does not establish voice interface compatibility.

## llama.cpp speech candidate

As of the check date above, the official `llama-tts` documentation includes an example running Qwen3-TTS Base with `libmtmd`, along with language and reference recording parameters. The following is a standalone upstream tool command, not a raradio command or evidence of validated raradio integration. See the [official TTS usage](https://github.com/ggml-org/llama.cpp/blob/master/tools/tts/README.md).

```sh
llama-tts \
  -hf ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF \
  --tts-lang zh \
  --tts-speaker-file reference.wav \
  -p "雨停了，明天再来这里。" \
  --output cloned.wav
```

Use the official instructions for the chosen llama.cpp version when preparing model files, companion components, and builds. raradio's existing MLX installation process neither installs `llama-tts` nor prepares its required GGUF files. This path has no raradio validation records for actual generation, quality, or recovery.

The semantics of reference recordings, transcripts, and emotion parameters also need checking before integration. Qwen's official documentation distinguishes cloning with audio plus a transcript from a mode using only speaker features, and notes that the latter may affect cloning quality. See the [Qwen3-TTS cloning documentation](https://github.com/QwenLM/Qwen3-TTS#voice-clone). raradio's MLX backend exposes `icl` and `xvector` configurations separately; comparisons of candidate backends must identify the mode actually used by each.

## Existing extension boundaries

raradio already separates character identity from voice configuration. JSON can be edited to choose preset voices or reference recordings for different characters. A voice configuration change invalidates the segments that use it; source text, manual attribution corrections, and unaffected audio are preserved. If several characters share a voice configuration, all of them are affected by changes to it.

Internal developer boundaries exist, but **there is no published third-party plugin SDK or mechanism for automatically discovering installed plugins**:

| Boundary | Existing interface and responsibility | Extension capabilities still needed |
| --- | --- | --- |
| Text analysis | `analyze(segments, characters) → AnalysisResult`; the project verifies that the source is unchanged and saves annotations | llama-server adapter, analyzer registration, separate service configuration |
| Speech synthesis | `Backend.synthesize(text, voice, emotion, output)`; `version` participates in caching | Backend registration, capability descriptions, plugin option validation, llama-tts adapter |
| Quality checks | Currently a fixed set of WAV structure and waveform checks | ASR, voice checks, and a checker extension interface |

The current CLI analyzer options and TTS factory still use built-in lists. Adding a Python backend also requires updating its registration point; writing a new `backend` name in JSON does not automatically load an external package. The existing fields of `VoiceProfile` are not a container for arbitrary plugin parameters either: unknown fields are rejected.

A future plugin interface should make adapters responsible for turning input into annotations or WAV files, while the core handles source text constraints, persistence, caching, bounded retries, human review, and export. A candidate design is a registration mechanism for explicitly selected Python packages loaded on demand. Each plugin should declare its own dependencies, version, and capabilities, such as reference recording support, transcript requirements, emotion instruction support, and output sample format. Unsupported parameters should produce explicit errors.

Plugins can call HTTP services or external binaries without maintaining a C++ fork for each plugin. Text adapters should encapsulate request formats, JSON responses, and service errors. Command-line TTS adapters should own argument lists, timeouts, cancellation, isolated temporary directories, output integrity, and cleanup. They should stop only processes they started; loading and unloading models on external shared services must follow those services' interfaces and the user's configuration.

## Implementation order

1. **Complete the validation baseline.** This repository provides `uv.lock`, a model-free workflow, and short-sample scenarios. Future real-model validation should record engine versions, weight versions, configurations, and results; an unchanged model name does not mean the files are unchanged.
2. **Add a second text backend.** Separate provider configuration from project business logic, then integrate llama-server first. Use the same annotation contract tests to verify source preservation, invalid JSON, timeouts, and context boundaries. Consider changing defaults only after users can select the backend through configuration.
3. **Validate a second voice backend.** Pin the llama.cpp build and GGUF version. First verify a small set of Chinese samples, cloning, truncation detection, and recovery from interruption, then connect it to raradio. Mark it experimental initially, without promising identical ICL, emotion, or speed settings to MLX.
4. **Use the second implementation to refine the plugin interface.** Extract the configuration and lifecycle behavior the implementations actually share, then provide a minimal example plugin, contract tests, error conventions, and a capability table. Install dependencies per backend; the core should not require every engine.
5. **Document backend support.** Adding a backend should include updates to platform documentation, dependencies, engine and model license links, a minimal example, and requirements for reporting failures. Public examples should use redistributable text and media; runtime data and model weights stay out of the source repository.

These steps are not all implemented, and no release dates are promised. The third-party extension interface should be settled only after a second implementation and contract tests exist.

## Evidence needed to change the default backend

Text comparisons should keep the model family, weight version, quantization level, chat template, context, and sampling settings as consistent as possible. Record cold starts, warm-run duration, peak memory, character attribution accuracy, JSON failure rate, human review volume, and recovery over long tasks. When quantization formats or implementations cannot be fully aligned, state the differences rather than attributing every difference to the engine.

Evaluate speech separately: omissions and repetitions on identical text and reference recordings, voice quality and prosody, generation time relative to audio duration, memory, failure rates, and resuming after cancellation. Start with blind listening to short samples, then validate whole chapters before attempting whole books. Community size and project counts provide context but cannot replace these measurements.

Evaluation results should determine the default backend. New adapters should remain compatible with existing character lists, manual corrections, and source text projects; changing the voice backend will require regeneration of the affected audio cache.
