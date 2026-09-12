# Usage Tradeoffs and Migration

English | [简体中文](usage-notes.zh-CN.md)

raradio currently supports a local TXT → character annotation → speech generation → chapter export workflow. Its MLX voice backend targets Apple Silicon Macs. Before starting batch generation, check character recognition, voices, and runtime with short samples. See the [Handbook](handbook.md) for installation and CLI commands, and [Architecture](architecture.md) for data contracts.

## Configure once, then handle exceptions

1. Import a short chapter first and complete character analysis. Confirm the IDs, clear aliases, and voice mappings for the narrator and main characters. Do not use generic pronouns such as “he” or “she” as fixed aliases for one person.
2. Generate a few representative sentences for each main voice: calm narration, ordinary dialogue, strong emotion, longer sentences, and character names. Listen before settling on the configuration, so unsuitable voices are caught before generating the entire book.
3. Run batch generation; rerunning resumes the work. Ordinary segments do not need individual confirmation, and the system tries bounded retries first.
4. Inspect the exception queue: fix characters for attribution issues, voices for configuration issues, and regenerate failed segments individually. Accept suspicious audio only after listening and approving it.
5. Export chapter WAV and SRT files once all segments are complete. Keep listening notes outside the export directory so they do not prevent later export replacement.

“Configure once” means confirmed characters and voices can be reused within the same book. New characters, ambiguous references, and model failures may still need attention. Rules analysis leaves dialogue for confirmation and is not a solution for automatic character identification across a whole novel.

## Choose the voice capabilities first

The table describes capabilities accepted by the current adapter; it does not imply that all TTS models have the same interface.

| Route | What it is useful for validating | Current limits |
| --- | --- | --- |
| Qwen3-TTS CustomVoice | Preset voices, character differentiation, and emotion and delivery instructions | Uses a preset `speaker` supported by the model; does not accept reference audio for cloning; emotion instructions still need listening validation |
| Qwen3-TTS Base | Voice similarity from reference audio | `strict` requires neutral; `reference` permits other emotion annotations but does not use them to control synthesis; neither accepts `instruct` |
| Diagnostic `tone` | State recovery, caching, chapter concatenation, and subtitles | Produces sine waves rather than speech; cannot be used to judge audiobook listening quality |

The current MLX adapter requires an explicit model, supports Base and CustomVoice, and requires the speed parameter to be `speed=1.0`. Unsupported capabilities raise errors so that parameters do not appear to be accepted without taking effect.

Base's `icl` cloning mode requires reference audio and an accurate transcript, as well as a model containing the required encoder. `xvector` mode uses voice features without the reference transcript. Reference files are copied into the project during configuration. With Base, `emotion_mode: reference` retains emotion annotations from analysis but does not send them as synthesis instructions or guarantee transfer of reference emotion or prosody. For characters requiring emotion instructions, CustomVoice can be used with listening checks to validate the effect.

A reference transcript must match what is actually spoken in the recording; a translation cannot replace a transcript in the original language. With cross-language reference recordings, validate voice similarity, target-language pronunciation, and emotion separately.

## What quality checks establish

Current automatic checks verify whether a WAV file is readable, PCM16, empty, or has truncated data, and flag silence, sparse signals, clipping, and unusual duration. Data truncation here means an incomplete file structure or sample count; it does not cover all omitted speech. Duration windows are broad and intended to catch obvious problems.

These checks cannot determine whether there are omissions, misreadings, repeated sentences, incorrectly pronounced proper names, wrong dialogue attribution, or incorrect voices. Keeping analyzers from rewriting the source does not guarantee that the synthesizer reads every word correctly. Passing waveform QA does not mean passing ASR proofreading or speaker identity verification.

Bounded retries can handle occasional generation failures, but they cannot fix unsupported backend parameters or missing reference files. Fix the configuration first when the same error repeats. Do not accept unheard audio in bulk just to clear the exception queue.

## Local operation and resources

Text analysis connects to local Ollama by default, and MLX synthesizes locally. The workflow does not require ongoing paid API calls. Model files and optional dependencies must be prepared separately; actual samples determine model loading behavior, speed, and voice results.

Memory requirements depend on the model, quantization, input length, and concurrent processes; the project has not established a general minimum-memory benchmark. Text analysis can be completed before speech synthesis begins. After Ollama analysis, the CLI requests that the model be unloaded and reports an unload failure. Record short-chapter runtime, retry counts, exception rates, and listening findings to decide whether the configuration suits longer tasks.

## Moving to another computer or archiving

1. Wait for current writes to finish, or stop generation normally, then copy the entire book project directory. Do not copy its parts separately while the database and audio are still being updated.
2. Keep `source.txt`, `project.json`, `cast.json`, `state.sqlite3`, `voices/`, and `audio/`. Copying only exported WAV files lets you keep listening but cannot restore per-segment generation state.
3. Install raradio and the optional backends needed on the target machine, and prepare the models previously used. Model caches and Python virtual environments are not part of the book project.
4. Check model identifiers in the voice configuration. Update absolute model paths for the new machine; reference audio within the project already uses relative paths.
5. Inspect the status first, then run a small generation check. Valid caches are reused; changes to model configuration or backend versions change affected generation fingerprints and require regeneration followed by validation.

Project write locking depends on POSIX `fcntl` and has no native Windows implementation yet; the MLX voice backend targets macOS / Apple Silicon. Copying data does not give every target operating system the same backend support. Keeping the same source, voice configuration, reference audio, and model versions across machines helps work continue, but sample listening is still advisable after changing the runtime environment.

EPUB import, M4B audiobook output, and a complete listening interface are not yet implemented. See the [Implementation Plan](plan.md) for future work.
