# Start with the examples

English | [简体中文](README.zh-CN.md)

Choose a scenario, follow “prepare → run → check the results” with a short sample, then move on to your own book. See the [handbook](../docs/handbook.md) for the complete parameters and troubleshooting.

Clone or download the repository, and run commands from the root containing `pyproject.toml`. The core workflow requires Python 3.11+ and a POSIX system; native Windows is not currently supported. Real speech requires an Apple Silicon Mac and Metal GPU.

Documentation language and synthesis language are independent. These examples keep their original Chinese text, character names, reference transcripts, and synthesis language settings in both documentation versions.

## Choose a scenario

| Scenario | Start here | Additional preparation | Manual and automatic work |
| --- | --- | --- | --- |
| 1. Two chapters, limited generation, and resuming | [Two-chapter diagnostic](#1-two-chapter-diagnostic) | No models or uv | Fully automatic; produces diagnostic tones |
| 2. Character review, single-segment regeneration, and voice changes | [Complete offline demonstration](#2-complete-offline-demonstration) | No models or uv | The script uses known answers from the sample to stand in for manual decisions |
| 3. One voice reads the whole text | [Single preset narrator](#3-single-preset-narrator) | MLX and a CustomVoice model | Choose a voice and listen; no Ollama required |
| 4. Different preset voices for different characters | [Multiple preset voices](#4-multiple-preset-voices) | An Ollama text model as well | The model suggests assignments; the user reviews uncertain cases |
| 5. Clone a voice from a recording | [xvector cloning](#5-xvector-cloning) | Base model and reference recording | Choose a recording and listen; no transcript or Ollama required |
| 6. Clone from a recording and accurate text | [ICL cloning](#6-icl-cloning) | Base encoder, recording, and transcript | The user checks the transcript; evaluation with a real model is not yet complete |
| 7. Clone only one character's voice | [Mixed voices](#7-mixed-voices) | Both types of TTS model, a recording, and Ollama | Confirm characters and voices, then handle exceptions |
| 8. Use your own novel | [Your own book](#8-your-own-book) | TXT, MLX, and an Ollama text model | Discover characters first, then confirm the complete cast |

The Chinese TXT files in this directory are original project content distributed under the [MIT license](../LICENSE). The characters, aliases, and voices demonstrate the workflow; they are not a recommended cast for arbitrary novels. Reference recordings, models, and generated output are not distributed with the source.

## Understand the output and paths first

- `work/…` stores resumable production projects; `output/…` stores exports. Use different directories for different scenarios and the same directory when resuming a project.
- When `build` / `run` returns valid JSON, `remaining: 0` means completion. If segments remain after reaching `--limit`, exit code `2` is expected. Argument errors may also return `2`, but without a JSON result; read stderr.
- `build --output` exports only when all work is complete. If there are no exported files, check `status` / `review`, follow the [review workflow](workflow.md), then use `run` and `export`. An empty `review` list may simply mean segments are still awaiting generation.
- In `segments`, `audio_path` is relative to the book's working directory. For example, `audio/abc.wav` in `work/single` refers to `work/single/audio/abc.wav`. On a Mac, open it in Finder or run `open` with the actual WAV path.
- Use a new working directory when comparing text analyzers, models, or source texts. Successful annotations are not automatically redone when you change `--analyzer` or `--model`.

Scenarios 1 and 2 run directly with Python and need no dependencies installed. For the MLX speech routes in scenarios 3–8, install [uv](https://docs.astral.sh/uv/getting-started/installation/) first, then run this once:

```sh
sh setup.sh mlx
```

This installs Python dependencies; TTS weights download separately on the first synthesis run. `sh setup.sh core` synchronizes the environment to core dependencies only; use `mlx` to retain the speech environment.

## 1. Two-chapter diagnostic

Prepare: Python 3.11+. **This example generates sine-wave diagnostic tones, not speech.**

```sh
python3 -m raradio build examples/chapters.txt --work work/chapters-diagnostic \
  --analyzer single-voice --cast examples/cast.tone.json --limit 2
python3 -m raradio status work/chapters-diagnostic
python3 -m raradio run work/chapters-diagnostic
python3 -m raradio export work/chapters-diagnostic --output output/chapters-diagnostic
```

The first command is expected to return `2` because it processes only two segments; the subsequent `run` completes the rest. Chapter titles are read too. Expected output:

```text
output/chapters-diagnostic/
├── chapter-0001.wav
├── chapter-0001.srt
├── chapter-0002.wav
├── chapter-0002.srt
├── manifest.json
└── playlist.m3u
```

Running `python3 -m raradio run work/chapters-diagnostic` again should reuse valid audio. All text belongs to narrator; no character analysis is performed. The shortest narration-only example uses `demo.txt + cast.tone.json + --analyzer rules`; see the repository [quick start](../README.md#quick-start-check-the-workflow).

## 2. Complete offline demonstration

Prepare: Python 3.11+; no models required.

```sh
python3 examples/offline_workflow.py
```

Each run creates a new directory under `work/`, prints its actual location and each CLI command, and keeps the results. It demonstrates character confirmation, dialogue review, limited generation, resuming, single-segment regeneration, changing only 小雨's voice, and two-chapter export.

The script uses **known answers from `chapters.txt` to stand in for manual decisions**. It does not recognize characters in arbitrary novels or automatically accept audio warnings. The two-chapter sample contains four actual dialogue lines and the quoted nickname “雨雨”; rules analysis leaves these quoted segments awaiting confirmation, and the nickname should be read by the narrator. The cast also demonstrates the aliases “雨雨／小雨” and “阿舟／林舟”.

The resulting `book/` directory can be inspected further with the CLI. `export/` contains two chapters of diagnostic tones and subtitles, and `verification.json` records checks from each stage. To perform the steps yourself, read [review, resume, and change voices](workflow.md).

## 3. Single preset narrator

Prepare: MLX and a CustomVoice model; no recording or Ollama required.

```sh
sh run.sh build examples/clone.txt --work work/single \
  --analyzer single-voice --cast examples/cast.single.json --limit 2
sh run.sh segments work/single
```

Listen to the generated per-segment WAV files first; both narration and dialogue use Serena. If satisfied, continue:

```sh
sh run.sh run work/single
sh run.sh export work/single --output output/single
```

Expected output includes `output/single/chapter-0001.wav`, subtitles, a manifest, and a playlist. To change the voice, copy and edit the complete configuration, then import it using the [change workflow](workflow.md#change-one-voice-and-keep-everyone-elses-results).

## 4. Multiple preset voices

Prepare: MLX, plus an installed and running [Ollama](https://ollama.com/) with a text model:

```sh
ollama pull qwen3:14b
sh run.sh build examples/story.txt --work work/preset-story \
  --analyzer ollama --cast examples/cast.mlx.json --limit 3
sh run.sh segments work/preset-story
sh run.sh review work/preset-story
```

The template assigns Serena, Vivian, and Ryan to the narrator, 小雨, and 林舟 respectively. Ollama suggests speaker assignments; results may still need review and are not guaranteed to be identical every time. After listening and handling exceptions:

```sh
sh run.sh run work/preset-story
sh run.sh export work/preset-story --output output/preset-story
```

The expected result is one chapter voiced by three characters. To try aliases and content spanning chapters, analyze `chapters.txt` in a new working directory. This practice text is not a character recognition accuracy benchmark.

## Prepare reference audio before cloning

Use a clear recording of yourself speaking alone, without backing music or overlapping speakers. The path below is a placeholder; replace it with a real file before running:

```sh
mkdir -p work/voice-config
cp "/path/to/your-reference.wav" work/voice-config/reference.wav
```

If you have no recording and only want to learn the workflow, first read the public `reference.txt` with a preset voice:

```sh
sh run.sh build examples/reference.txt --work work/reference-demo \
  --analyzer single-voice --cast examples/cast.single.json \
  --output output/reference-demo
mkdir -p work/voice-config
cp output/reference-demo/chapter-0001.wav work/voice-config/reference.wav
```

Copy the file only after generation and export are complete. This reference comes from synthesized speech and only demonstrates the cloning workflow; it cannot evaluate similarity to a real person's voice. Before using ICL, still listen and check the transcript; do not assume the synthesizer read every word correctly.

`reference_audio: "reference.wav"` is relative to the **JSON file's directory**; a real absolute path also works. JSON values do not expand `~` or `$HOME`. On import, raradio copies the recording into the book's `voices/` directory. Reference audio is separate from the text to be read: the target text below is `clone.txt`.

## 5. xvector cloning

Prepare: MLX, a Base model, and `work/voice-config/reference.wav` created using the [reference audio preparation](#prepare-reference-audio-before-cloning) steps. No transcript or Ollama required.

```sh
cp examples/cast.clone.xvector.json work/voice-config/cast.xvector.json
sh run.sh build examples/clone.txt --work work/clone-xvector \
  --analyzer single-voice --cast work/voice-config/cast.xvector.json --limit 2
sh run.sh segments work/clone-xvector
sh run.sh review work/clone-xvector
```

After listening, continue and export:

```sh
sh run.sh run work/clone-xvector
sh run.sh export work/clone-xvector --output output/clone-xvector
```

The expected result is one chapter with every segment using the reference voice route. Do not add `reference_text`, a preset `speaker`, or `instruct`. A short sample has been run with a real model, but cloning similarity has not been evaluated.

## 6. ICL cloning

Prepare: MLX, a Base model with the required encoder, a recording, and **an accurate transcript of what the recording actually says**. First create `work/voice-config/reference.wav` using the [reference audio preparation](#prepare-reference-audio-before-cloning) steps. This route has adapter contract tests, but quality evaluation with a real model is not yet complete.

```sh
cp examples/cast.clone.icl.json work/voice-config/cast.icl.json
```

Open the copied JSON and replace the prompt in `reference_text` with the full text actually spoken in the recording before running the next commands. For a Japanese recording, enter the original Japanese words, not a Chinese translation; `language: "Chinese"` is the target synthesis language. Do not enter the target text from `clone.txt`.

```sh
sh run.sh build examples/clone.txt --work work/clone-icl \
  --analyzer single-voice --cast work/voice-config/cast.icl.json --limit 2
sh run.sh segments work/clone-icl
sh run.sh review work/clone-icl
```

After listening and resolving issues:

```sh
sh run.sh run work/clone-icl
sh run.sh export work/clone-icl --output output/clone-icl
```

Keep separate directories when comparing the two modes. A missing encoder requires a compatible model; if switching to xvector, remove the transcript as well. Base cloning does not support general emotion instructions. The template's `emotion_mode: reference` allows analyzed emotions to be retained without sending control instructions to Base; it does not guarantee accurate reproduction of reference prosody or annotated emotions.

## 7. Mixed voices

Prepare: MLX, CustomVoice and Base models, a running Ollama service, and `qwen3:14b`. First create `work/voice-config/reference.wav` using the [reference audio preparation](#prepare-reference-audio-before-cloning) steps; see [scenario 4](#4-multiple-preset-voices) for Ollama setup.

```sh
cp examples/cast.mixed.json work/voice-config/cast.mixed.json
sh run.sh build examples/story.txt --work work/mixed \
  --analyzer ollama --cast work/voice-config/cast.mixed.json --limit 3
sh run.sh segments work/mixed
sh run.sh review work/mixed
```

The template uses xvector cloning for 小雨, Serena for the narrator, and Ryan for 林舟. After listening and handling pending work:

```sh
sh run.sh run work/mixed
sh run.sh export work/mixed --output output/mixed
```

The expected result is one chapter mixing cloned and preset voices. The current MLX backend keeps only one model loaded, so alternating between the two model types may reload them repeatedly. Do not mix fields specific to Base and CustomVoice; both routes require `speed: 1.0`.

## 8. Your own book

Prepare: MLX and your chosen TTS model, then complete the Ollama setup in [scenario 4](#4-multiple-preset-voices), start the service, and run `ollama pull qwen3:14b`. Here, `analyze` requires Ollama by default; for a single narrator, use [scenario 3](#3-single-preset-narrator). Input can be UTF-8 TXT or UTF-16 TXT with a BOM. Replace the path below with a real file; `work/my-book` must be a new directory:

```sh
sh run.sh init "/path/to/book.txt" --work work/my-book
sh run.sh analyze work/my-book
sh run.sh cast work/my-book > work/my-book/cast.edit.json
```

The next step is manual: retain the actual character IDs, add voices, and confirm the cast. See [edit the complete cast and voices](../docs/handbook.md#2-edit-the-complete-cast-and-voices) for complete JSON and examples of shared and separate voices. Import **replaces the entire cast and voice tables**. Do not submit only a few changed rows or simply apply the example cast to your book.

```sh
sh run.sh cast work/my-book --file work/my-book/cast.edit.json
sh run.sh run work/my-book --limit 5
sh run.sh segments work/my-book
sh run.sh review work/my-book
```

Listen and handle exceptions first, then continue with `run` and `export`. You do not need to confirm every normal segment individually. See [review and voice changes](workflow.md) for everyday edits.

## Keeping the examples working

After editing examples, maintainers should run:

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

Regression checks read the public texts and configurations and exercise the CLI, reference file import, export, and caching. Contract tests substitute model loading and inference, so passing does not establish real speech quality. For new speech models, still run a short sample and record versions following the [verification instructions](../docs/verification.md).
