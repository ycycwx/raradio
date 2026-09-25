# raradio Handbook

English | [简体中文](handbook.zh-CN.md)

raradio turns a TXT file into an audiobook project you can keep working on: it splits the original text, determines who reads each segment and which voice to use, generates and checks the audio segment by segment, then exports chapter audio. You can start with a short sample, listen, and continue with the whole book. Stopping partway through, changing a character's voice, or correcting a line of dialogue does not require generating everything again.

For installation and the shortest first sample, see [Install raradio](installation.md). For unmarked manuscripts, Japanese encodings, changing analysis modes, and repairing segment boundaries, see [Manuscript formats and structure repair](text-input.md).

Keep three things separate: **the TXT file is your input, `work/my-book/` is the resumable production project, and `output/my-book/` holds the finished files for your player**. Models and the Python environment are not part of the book project. Keep the working directory so you can change voices, finish missing work, or move the project later.

For your first run, read “Environment, files, and paths,” “Scenario 1,” and “Scenario 2” in order. If you already have a voice sample, continue with the cloning scenarios. For a new book, follow “Scenario 7: Make an audiobook from your own novel with multiple characters.”

## Contents

- [What raradio automates and what you decide](#what-raradio-automates-and-what-you-decide)
- [Environment, files, and paths](#environment-files-and-paths)
- [Scenario 1: Check the workflow without downloading models](#scenario-1-check-the-workflow-without-downloading-models)
- [Scenario 2: Read a short story with preset voices](#scenario-2-read-a-short-story-with-preset-voices)
- [Scenario 3: Use one voice for everything, including dialogue](#scenario-3-use-one-voice-for-everything-including-dialogue)
- [Scenario 4: Clone with xvector using audio without a transcript](#scenario-4-clone-with-xvector-using-audio-without-a-transcript)
- [Scenario 5: Clone with ICL using audio and an accurate transcript](#scenario-5-clone-with-icl-using-audio-and-an-accurate-transcript)
- [Scenario 6: Mix narration, preset character voices, and cloned voices](#scenario-6-mix-narration-preset-character-voices-and-cloned-voices)
- [Scenario 7: Make an audiobook from your own novel with multiple characters](#scenario-7-make-an-audiobook-from-your-own-novel-with-multiple-characters)
- [Listen to samples, inspect status, and understand exit codes](#listen-to-samples-inspect-status-and-understand-exit-codes)
- [Fix attribution, audio, and configuration problems](#fix-attribution-audio-and-configuration-problems)
- [Run a whole book, stop, resume, and make another version](#run-a-whole-book-stop-resume-and-make-another-version)
- [Move the project to another machine](#move-the-project-to-another-machine)
- [Change text models, TTS models, and runtime backends](#change-text-models-tts-models-and-runtime-backends)
- [Verification scope and reproduction](#verification-scope-and-reproduction)
- [Current extensions and possible future plugins](#current-extensions-and-possible-future-plugins)

## What raradio automates and what you decide

| Stage | What raradio currently does automatically | What you need to do |
| --- | --- | --- |
| Import | Reads TXT, saves an immutable copy of the source, splits it by chapter headings, quotation marks, and length, and preserves source positions | Provide a readable TXT file; to revise the text, edit the input first and create a new project |
| One voice | `single-voice` assigns all narration and dialogue to `narrator`, with neutral emotion | Choose a voice |
| Character analysis | Ollama proposes characters, aliases, dialogue attribution, and emotions from context; conservative rules mode identifies only narration | Confirm the character list, voices, and aliases; resolve uncertain attributions |
| Voice configuration | Saves character-to-voice mappings and copies reference audio into the working directory | Choose preset voices or prepare reference audio for cloning; ICL also needs an accurate transcript |
| Generation | Calls the voice model for each segment, keeps completed results, and allows up to 3 attempts per segment by default | Listen to a few representative segments before deciding to generate in bulk |
| Checks | Checks WAV files, empty audio, silence, clipping, and clearly abnormal durations, and records warnings | Listen for misread, missing, or repeated text, incorrect speakers, and unsuitable voice character or emotion |
| Repair | Regenerates affected segments when configuration or attribution changes; keeps other valid segments | Fix the cause, request individual retries when needed, and accept audio warnings only after listening |
| Export | Once every segment is complete, joins chapter WAV files and generates SRT subtitles, a playlist, and a source manifest | Listen to the finished book in a player, and keep the working directory for later edits |

The model's `confidence` is its own assessment of a character annotation, **not a measured accuracy rate**. Attributions below 0.8 currently go to review; those above the threshold can still identify the wrong character. raradio does not automatically choose voices for newly discovered characters or confirm them for you.

There is currently no automatic transcription of reference audio, no ASR check of generated speech against the text, no voice identity check, and no listening-quality score for the whole book. Subtitles use the original text segments and actual audio durations: they are segment-level subtitles, not speech recognition results. raradio does not rewrite the source text; this does not guarantee that the synthesizer will read every word correctly.

## Environment, files, and paths

### Where to run commands

Run the commands in this handbook from the raradio source root: the directory containing `setup.sh`, `run.sh`, and `examples/`. First enter your source directory, replacing `/path/to/raradio` with its actual location:

```sh
cd /path/to/raradio
```

The paths `work/my-book`, `configs/`, and `output/` below are relative to this root. `/path/to/`, `SEGMENT_ID`, and `ACTUAL_FILENAME` in examples are placeholders; replace them before running the commands.

`sh /path/to/run.sh`, an installed `raradio`, and `python3 -m raradio` resolve relative command-line paths from your current directory. The runner locates the repository's environment without changing the directory used for your book paths. Put paths containing spaces in double quotes, such as `"/path/to/Books/My Book.txt"`. Examples below are run from the repository root, where the supplied `examples/` files live.

Reference files in voice configurations follow a separate rule: `reference_audio` is relative to **the directory containing the JSON file** passed to `cast --file` or `build --cast`. For example, `"reference_audio": "voices/reader.wav"` in `configs/cast.clone.json` refers to `configs/voices/reader.wav`. Absolute paths also work. Paths in JSON do not expand `~` or `$HOME`; use an actual absolute or relative path. After a successful import, raradio copies the reference file into the book's `voices/` directory and no longer depends on its original location.

### Check the workflow only: core environment

You need Python 3.11 or later and a POSIX system with `fcntl` file locks; native Windows is not currently supported. The core uses only the Python standard library, so running `python3 -m raradio` from source does not require installing voice models. To use `sh run.sh` throughout this handbook, prepare `uv` and then install the core environment:

```sh
sh setup.sh core
sh run.sh doctor
```

The setup script prompts you if `uv` is missing; on a Mac with Homebrew, you can first run `brew install uv`. `setup.sh core` prepares only the core CLI and cannot generate human speech. It synchronizes the environment to the core dependencies and removes installed optional speech dependencies; use `sh setup.sh mlx` when you need to keep the speech environment.

### Generate speech: MLX environment

The current speech backend targets Apple Silicon Macs with macOS 14+ and requires access to a Metal GPU. The source setup selects Python 3.11 using `.python-version`; uv downloads it if needed. Core support for newer Python versions does not establish compatibility of every optional speech dependency. Install the project's pinned Python dependencies:

```sh
sh setup.sh mlx
sh run.sh setup
```

The script installs from `uv.lock`; the MLX-Audio version is pinned in `pyproject.toml`. Installing `mlx` dependencies and downloading TTS models are separate steps: the Hugging Face models in the examples are usually downloaded on the first synthesis call, with existing caches reused. The first run takes longer than later runs, so do not estimate whole-book speed from the first run's total time alone.

### Identify characters automatically: also prepare Ollama

Ollama is needed only when you select `--analyzer ollama`. Preset voices and voice cloning do not themselves require Ollama; you can skip it entirely when reading everything with one voice.

After installing and starting Ollama, prepare the default text model:

```sh
ollama pull qwen3:14b
sh run.sh doctor --profile ollama --model qwen3:14b
```

The default connection is `http://localhost:11434`. `setup` defaults to the single-voice path and does not contact Ollama; `setup --mode multi-voice` checks both speech and Ollama requirements. It prints a readable report by default and accepts `--format json`. `doctor` remains the lower-level profile check: its core profile makes no network requests, while `--profile ollama` queries the selected service for `--model`. Exit status is `0` when selected checks pass or `1` when a prerequisite fails. These checks do not install anything, initialize Metal, download or load TTS weights, run text analysis, or validate listening quality. FFmpeg is not required for the current WAV export. Use `sh run.sh --version` to report the raradio version.

### Online preparation and offline use

Prepare Python dependencies, Ollama text models, and Hugging Face TTS models separately. `setup.sh` does not pull Ollama models, and raradio's analysis does not automatically install missing text models. Complete a short sample of your chosen workflow while online to confirm that the model and its supporting files are all cached, then use the same configuration offline. Having the dependencies installed is not enough to guarantee successful offline synthesis.

A workflow using local Ollama and local MLX does not need ongoing calls to paid APIs. Cache locations are managed by their respective runtimes and are outside `work/my-book/`; consider them separately when backing up or moving a project. You can also set `model` in `voices` to the absolute path of a local model you have already prepared.

### Files to prepare

| What you want to do | What to prepare |
| --- | --- |
| Diagnose the workflow | The repository's TXT file and `cast.tone.json` |
| Read with one preset voice | TXT and a voice JSON mapping only the narrator; no reference audio |
| Use multiple preset voices | TXT, an Ollama model, and confirmed mappings for all characters and voices |
| Clone with xvector | TXT, a Base model, and a clear recording of one speaker; omit the transcript |
| Clone with ICL | The files above, an accurate transcript of what the reference audio actually says, and a model with the required encoders |
| Clone just one voice in a cast | The complete character list, that character's reference audio, and preset voice configurations for the others |

Use UTF-8 TXT or UTF-16/UTF-32 TXT with a BOM. For other text encodings, pass the actual encoding with `--encoding`, such as `--encoding cp932`; see [manuscript formats](text-input.md). Convert EPUB and PDF to TXT with an external tool first. Start testing a clone with a short recording containing only the target speaker and little background interference. The program does not currently remove accompaniment, separate multiple speakers, or find the best reference clip for you.

## Scenario 1: Check the workflow without downloading models

This scenario checks import, generation state, resuming, subtitles, and export. It produces diagnostic sine-wave tones.

If you have installed the core environment:

```sh
sh run.sh build examples/demo.txt --work work/diagnostic \
  --analyzer rules --cast examples/cast.tone.json --output output/diagnostic
```

Without installing the environment, you can also run directly from source:

```sh
python3 -m raradio build examples/demo.txt --work work/diagnostic \
  --analyzer rules --cast examples/cast.tone.json --output output/diagnostic
```

Choose either command. When it finishes, `output/diagnostic/` contains `chapter-0001.wav`, the matching `.srt`, `playlist.m3u`, and `manifest.json`. Running the same command again reuses valid completed audio.

This example has no dialogue requiring speaker identification. `rules` does not automatically identify who speaks dialogue: replacing the input with a novel containing dialogue will usually leave those lines awaiting human confirmation. To have one person read everything, use `single-voice` as described below.

## Scenario 2: Read a short story with preset voices

You need the MLX environment, Ollama, and `qwen3:14b`. No reference recording is needed.

```sh
sh run.sh build examples/story.txt --work work/preset-story \
  --cast examples/cast.mlx.json --output output/preset-story
```

`examples/story.txt` is an original short dialogue. The example JSON confirms the narrator (`narrator`), 小雨 (`xiaoyu`), and 林舟 (`linzhou`), using the CustomVoice presets Serena, Vivian, and Ryan respectively. Ollama assigns dialogue to these characters. Uncertain annotations remain as tasks you can inspect with `review`.

When it finishes, listen to `output/preset-story/chapter-0001.wav`. This example checks that the three voices work within the production workflow; it does not replace a long-form evaluation. When using your own novel, do not keep these three example characters as the full cast. Follow the workflow for your own novel to discover and confirm its actual characters.

## Scenario 3: Use one voice for everything, including dialogue

If you want the same narrator to read the entire text, you do not need to identify the characters first. `--analyzer single-voice` assigns text both inside and outside quotation marks to `narrator`, with all emotions set to `neutral`. It preserves the original text, dialogue segmentation, and chapters.

Copy the single-voice template to your own configuration directory; edit the copy if you want a different voice:

```sh
mkdir -p configs
cp examples/cast.single.json configs/cast.single.json
```

```json
{
  "characters": {
    "narrator": {
      "name": "旁白",
      "aliases": [],
      "voice": "narrator",
      "confirmed": true
    }
  },
  "voices": {
    "narrator": {
      "backend": "mlx",
      "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
      "speaker": "Serena",
      "instruct": "自然朗读，声音清晰，语气平稳。",
      "language": "Chinese",
      "speed": 1.0,
      "seed": 42
    }
  }
}
```

The example above shows the complete configuration structure; you can also leave the template as it is. `characters.narrator.voice` must match a key in `voices`. In JSON, `true` and the numbers `1.0` and `42` are unquoted; strings use double quotes. Do not add comments or trailing commas.

Try the short example containing dialogue:

```sh
sh run.sh build examples/story.txt --work work/single-story \
  --analyzer single-voice --cast configs/cast.single.json \
  --output output/single-story
```

For your own longer work, replace the input path with your TXT, choose a new `--work` directory, and start with `--limit 5`. This counts segments actually processed in the current invocation; it does not guarantee coverage of different sentence types. After listening, continue with `sh run.sh run work/my-book`, using your book's working directory.

If you later want multiple voices for the same book, create a new working directory and analyze it again. Changing the `--analyzer` argument does not automatically reannotate an already annotated project in full.

## Scenario 4: Clone with xvector using audio without a transcript

Use a Base model to extract voice characteristics from reference audio. This mode does not use a reference transcript and does not generate one for you. Start with one cloned voice reading everything so you can judge the voice on its own; Ollama is not needed.

Copy the template:

```sh
mkdir -p configs
cp examples/cast.clone.xvector.json configs/cast.clone.xvector.json
```

Open `configs/cast.clone.xvector.json` and change `reference_audio` to the absolute path of your recording. The relevant voice fields should be:

```json
{
  "backend": "mlx",
  "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit",
  "reference_audio": "/path/to/recordings/reader.wav",
  "clone_mode": "xvector",
  "emotion_mode": "reference",
  "language": "Chinese",
  "speed": 1.0,
  "seed": 42
}
```

This is one voice entry within `voices`; the template already contains the complete `characters` and `voices` structure. `/path/to/recordings/reader.wav` is a placeholder and must be replaced with an existing file. Do not add `reference_text`, a preset `speaker`, or `instruct`.

```sh
sh run.sh build examples/clone.txt --work work/clone-xvector \
  --analyzer single-voice --cast configs/cast.clone.xvector.json \
  --limit 3
sh run.sh segments work/clone-xvector
```

Listen to the generated segments using the path guidance below. Once satisfied, continue and export:

```sh
sh run.sh run work/clone-xvector
sh run.sh review work/clone-xvector
sh run.sh export work/clone-xvector --output output/clone-xvector
```

For Base, `emotion_mode: reference` allows this cloning workflow to process segments with emotion annotations without turning those annotations into unsupported emotion instructions. **It does not guarantee accurate transfer of the reference recording's emotion, rhythm, or prosody**, nor does it automatically realize emotions such as happy or sad identified in the novel. You need to listen to the actual result.

Base's default `emotion_mode: strict` accepts only neutral emotion. Single-voice annotations are already neutral, so strict also works there. Choosing reference in a cast with multiple characters makes a voice-level decision not to treat analyzed emotions as a control capability of Base.

## Scenario 5: Clone with ICL using audio and an accurate transcript

ICL requires matching audio and text, and the selected Base model must include a speaker encoder and a speech tokenizer encoder. The template does not prepare those files for you.

```sh
mkdir -p configs
cp examples/cast.clone.icl.json configs/cast.clone.icl.json
```

Edit the copied template:

- Set `reference_audio` to the real file path; an absolute path is a good choice for your first attempt.
- Set `reference_text` to the words actually spoken in the recording, checking each sentence against the audio.
- Keep `clone_mode: "icl"` and use a Base TTS model.
- Do not set a preset `speaker` or `instruct`; keep `speed` at `1.0`.

For example, only if the recording actually says “雨停了，我们回家吧。” should the two fields be:

```json
{
  "reference_audio": "/path/to/recordings/reader.wav",
  "reference_text": "雨停了，我们回家吧。"
}
```

This small object illustrates the fields to edit; it cannot replace the full configuration on its own. If the audio is in Japanese, the transcript must contain the actual Japanese words, not a Chinese translation. `language: "Chinese"` specifies the desired language of the generated speech. It does not translate the reference audio or demonstrate the quality of cross-language cloning.

```sh
sh run.sh build examples/clone.txt --work work/clone-icl \
  --analyzer single-voice --cast configs/cast.clone.icl.json --limit 3
sh run.sh segments work/clone-icl
```

After listening and approving the result, `run` the remaining content and `export`. If an encoder is missing, an accurate transcript cannot supply the missing model capability. Prepare a compatible Base model, or explicitly switch to xvector and remove `reference_text`.

ICL's automated tests use substitute models to check parameters and adapter contracts; they do not demonstrate real speech quality. The project has not yet completed real ICL inference and listening evaluation. To compare ICL with xvector, create two short projects using the same recording and keep each configuration and your listening conclusions.

## Scenario 6: Mix narration, preset character voices, and cloned voices

Character identity and voice configuration are separate. Each entry in `characters` uses `voice` to point to a configuration in `voices`; multiple characters may share the same voice. A project can use CustomVoice presets and Base clones together, but a single voice configuration must not mix parameters specific to the two model types.

```sh
mkdir -p configs
cp examples/cast.mixed.json configs/cast.mixed.json
```

The template uses Serena for the narrator, Ryan for 林舟, and a Base xvector clone for 小雨. Change `reference_audio` in 小雨's voice configuration to your recording's actual path. The characters match `examples/story.txt`, so this short story lets you hear preset and cloned voices together.

```sh
sh run.sh build examples/story.txt --work work/mixed-story \
  --cast configs/cast.mixed.json --limit 5
sh run.sh segments work/mixed-story
sh run.sh review work/mixed-story
```

This scenario needs Ollama to analyze dialogue attribution. Each voice can use `mlx` as its `backend`, with Base or CustomVoice selected separately in `model`. CustomVoice uses `speaker` and optionally `instruct`; Base uses `reference_audio` and the corresponding cloning mode. Detecting emotions during analysis does not mean both model types have the same emotion controls.

When mixing models, the current MLX backend keeps only one model loaded and switches as needed in segment order. Listen to a short sample and observe the time it takes before deciding to use this setup for the whole book. Apply the same configuration approach to your own novel; do not overwrite its discovered character list with the template.

## Scenario 7: Make an audiobook from your own novel with multiple characters

This workflow separates character discovery, human confirmation, and production generation. It suits a new book whose characters are not yet known. Prepare Ollama and your chosen speech environment first; replace the example input `/path/to/book.txt` with your actual path.

### 1. Import and discover characters

```sh
sh run.sh init /path/to/book.txt --work work/my-book
sh run.sh analyze work/my-book
sh run.sh status work/my-book
sh run.sh cast work/my-book > work/my-book/cast.edit.json
```

`init` requires a working directory that does not yet exist and saves an immutable copy of the source. The default maximum segment length is about 240 characters. For shorter segments, add `--max-chars 160` at the first import. Segmentation includes chapter headings and body text; headings are read aloud too. To change the segment length, create a new project from the original TXT.

`analyze` uses Ollama by default and saves results by chapter. The model receives batches with nearby context and existing characters. Discovered characters usually remain `confirmed: false`: this asks you to choose voices first and does not mean analysis failed.

### 2. Edit the complete cast and voices

Open `work/my-book/cast.edit.json`, preserve every discovered character ID, and work through each entry: check `name`, organize unambiguous `aliases`, assign a `voice`, and set `confirmed: true` once satisfied. The narrator always uses `narrator`. Character IDs link later attributions to voice mappings; do not change them arbitrarily because names look similar.

For example, if a character was discovered as `xiaoyu`, keep that ID; you can add “雨雨” as a confirmed alias. Do not permanently bind generic pronouns or references such as “他” (“he”), “她” (“she”), or “那个人” (“that person”) to one character. The model still needs context to resolve them.

Add voices to `voices` in the same JSON, using the fields from the scenarios above. Preset voices do not need reference audio; clone reference paths are resolved relative to this JSON's directory. This handbook puts the editing file inside `work/my-book/` so that existing references such as `voices/CONTENT_HASH.wav` stay valid.

For example, **only if your exported character IDs are exactly the three below**, you can organize them into this complete configuration. The narrator and 小雨 share `shared`, while 林舟 has a separate voice. If your export has different IDs or more characters, preserve them. Edit `voice` and `confirmed` in the original list and add the corresponding voices; do not replace it with the example cast.

```json
{
  "characters": {
    "narrator": {"name": "旁白", "aliases": [], "voice": "shared", "confirmed": true},
    "xiaoyu": {"name": "小雨", "aliases": ["雨雨"], "voice": "shared", "confirmed": true},
    "linzhou": {"name": "林舟", "aliases": ["阿舟"], "voice": "linzhou", "confirmed": true}
  },
  "voices": {
    "shared": {
      "backend": "mlx",
      "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
      "speaker": "Serena",
      "language": "Chinese",
      "instruct": "自然朗读，清晰、平稳。",
      "seed": 42
    },
    "linzhou": {
      "backend": "mlx",
      "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
      "speaker": "Ryan",
      "language": "Chinese",
      "instruct": "自然地说话，温和、放松。",
      "seed": 43
    }
  }
}
```

`characters` describes who is in the book; `voices` describes the available voice configurations. They are linked by the value of `voice`. To give 小雨 her own voice, add an entry to `voices` and change her `voice` value. Editing `shared` affects every character that points to it. For a complete exercise that needs no models, see the [review and voice-change example](../examples/workflow.md).

**Importing a cast replaces the entire character and voice tables; it does not merge a partial patch.** Even when changing just one person's voice, start from the current complete export and keep every discovered character and every other voice configuration. Segments assigned to omitted characters will otherwise lose confirmation or their voice mapping.

```sh
sh run.sh cast work/my-book --file work/my-book/cast.edit.json
sh run.sh review work/my-book
```

After character confirmation, segments with sufficiently clear attributions automatically become `READY`. Resolve any remaining review items according to their `issue`; you do not need to confirm every normal segment individually.

### 3. Generate a small amount first

```sh
sh run.sh run work/my-book --limit 5
sh run.sh segments work/my-book
```

Listen to this batch before continuing. `--limit 5` limits only how many segments this invocation processes; individual segments may still be retried internally. It does not select a sample covering every character, emotion, or proper name. If the opening is all narration, run another small batch or create a separate short TXT sample project with representative sentences.

Choose listening material that covers the voices you care about, ordinary dialogue, longer sentences, emotion changes, and names. If a voice is unsatisfactory, edit and reimport the configuration, then listen to new samples before continuing. This makes the result easier to judge than changing voices after generating the entire book.

### 4. Continue, resolve exceptions, and export

```sh
sh run.sh run work/my-book
sh run.sh review work/my-book
sh run.sh status work/my-book
```

If anything goes wrong, use the repair steps below, then continue with `run`. Export requires `remaining` in `status` to be `0`:

```sh
sh run.sh export work/my-book --output output/my-book
```

The export directory contains chapter WAV files, segment-level SRT subtitles, a playlist, and `manifest.json`, which records source text segments and check results. Direct MP3/M4B export is not currently available. To change pauses between segments, export again with an option such as `--pause-ms 250`; this does not resynthesize individual segments. Keep listening notes and other personal files outside the export directory. When exporting again, raradio checks that the directory belongs to its export and refuses to overwrite a directory containing unrelated files.

## Listen to samples, inspect status, and understand exit codes

The three inspection commands serve different purposes:

```sh
sh run.sh status work/my-book
sh run.sh segments work/my-book
sh run.sh review work/my-book
```

`status` summarizes counts. `segments` shows the source text, character, emotion, state, audio path, and QA results for every segment. `review` lists only `NEEDS_REVIEW` and `FAILED` items. An empty `review` therefore does not mean the whole book is complete: segments may still be unanalyzed, queued for generation, or interrupted. Check `status.remaining` as well.

| State | Meaning | Next step |
| --- | --- | --- |
| `PENDING_PARSE` | Text analysis is not complete | Run `analyze` |
| `READY` | Annotations and voice mappings are usable | Run `run` |
| `GENERATING` | The previous generation is still running or was interrupted here | Confirm the old process has stopped, then run `run` |
| `DONE` | Audio checks passed, or you accepted this segment's current audio | Valid cached audio can be reused |
| `NEEDS_REVIEW` | A character, annotation, reference file, or audio warning needs attention | Read the segment's `issue` |
| `FAILED` | Generation failed after multiple attempts | Fix the cause, then `retry` and `run` |

The `audio_path` returned by `segments` is **relative to the book's working directory**. For example, if a segment in `work/my-book` has `audio/abc.wav`, the actual file is `work/my-book/audio/abc.wav`. On a Mac, open it in Finder or substitute the actual path in:

```sh
open work/my-book/audio/ACTUAL_FILENAME.wav
```

A segment without an `audio_path` has no usable audio to listen to yet. Once a whole chapter is complete and exported, open `output/my-book/chapter-0001.wav`.

Workflow commands write JSON results to stdout and synthesis progress and model logs to stderr. `--help`, `--version`, `setup`, and `agent-guide` output text; the latter two accept `--format json`. Redirect the JSON to save a status snapshot, for example: `sh run.sh status work/my-book > work/my-book/status.snapshot.json`.

`build` and `run` use these exit codes:

| Exit code | Meaning |
| --- | --- |
| `0` | All segments are complete |
| `2` | With a valid JSON result, some work remains: `--limit` may simply have been reached, or segments may await confirmation or have failed. Argument parsing errors also use this code, but produce no JSON result |
| `1` | A configuration, path, or runtime error was caught during execution; read stderr |
| `130` | Interrupted by Ctrl+C; progress is saved and can be resumed |

A run that successfully generates five segments with `--limit 5` and then returns `2` has not necessarily crashed. Commands in this handbook appear on separate lines so you can continue inspecting results. In automated shell scripts, handle `2` by checking for valid JSON on stdout and reading stderr. Do not use `set -e` or `&&` in a way that treats every `2` as an immediate fatal error, and do not treat missing arguments or misspelled options as a normal resumable run. The exit code from `analyze` is also no substitute for checking state: analysis service failures may be recorded in a segment's `issue`, so read the output and `review`.

## Fix attribution, audio, and configuration problems

First read the `issue` in `review` and match its cause to the action needed. Replace `SEGMENT_ID` below with a real ID from `review` or `segments`, and use character IDs from the current `cast`.

### A line has the wrong speaker or an uncertain attribution

First confirm that the target character exists, is `confirmed: true`, and has a voice. Then correct the segment:

```sh
sh run.sh resolve work/my-book SEGMENT_ID --speaker xiaoyu --emotion happy
sh run.sh run work/my-book
```

Omit `--emotion` if the emotion does not need changing. `resolve` saves the human attribution and causes the affected segment to be regenerated; you usually do not need to follow it with `retry`. Human corrections are preserved during recovery from later analysis failures.

If a character simply needs confirmation or a voice, edit and import the complete cast instead of calling `resolve` for every line. To assign a segment to the narrator, use `--speaker narrator`.

### Ollama is unreachable, the model is missing, or annotations are invalid

Check that Ollama is running, `doctor --profile ollama --model YOUR_MODEL` lists the selected text model, and the configured URL is correct. After fixing the service:

```sh
sh run.sh analyze work/my-book
sh run.sh review work/my-book
```

Successfully saved analysis is not all rerun, and human corrections are preserved. If long segments or slow models time out, increase the timeout with `--timeout 300` or reduce the batch size with `--batch-size 12` for unfinished analysis. `--timeout` is the limit for each batch request, not a deadline for the whole book.

### Audio warnings: `audio: silence`, `clipping`, `too_short`, and others

These segments already have a current file you can listen to. Listen first: regenerate the segment if it is unsatisfactory, and accept the warning only if you approve the current audio.

```sh
sh run.sh retry work/my-book SEGMENT_ID
sh run.sh run work/my-book
```

If you decide to keep the current audio after listening, use this command instead of regenerating:

```sh
sh run.sh accept-audio work/my-book SEGMENT_ID
```

`accept-audio` accepts only the waveform QA warnings for the current audio. It does not unconditionally approve every problem. It cannot confirm characters or accept audio that is missing, modified, or no longer matches the current configuration. Even if a segment is already `DONE`, you can still use `retry` to regenerate it after hearing a misreading or an unsatisfactory result.

### `generation:` reports unsupported parameters

Changing the random seed will not fix the same configuration error. Correct and reimport the complete voice configuration first:

| Common case | How to fix it |
| --- | --- |
| Base has `instruct` or a preset `speaker` | Remove those fields; Base uses reference audio |
| Base in strict mode encounters a non-neutral emotion | If the line should be calm, correct it to neutral. If you decide not to require explicit emotion control, set `emotion_mode: "reference"` for that voice. If you need instruction-based control, evaluate CustomVoice |
| xvector also has `reference_text` | Remove the transcript field |
| ICL lacks an accurate transcript or the model lacks required encoders | Supply the actual transcript and a compatible model, or explicitly switch to xvector and remove the transcript |
| CustomVoice has reference audio, `emotion_mode: "reference"`, or xvector mode | Remove reference audio and text; use strict and omit `clone_mode` |
| The model does not support the `speaker` name or `language` | Use values the model actually supports; a speaker error lists available voices |
| Qwen3-TTS has a `speed` other than `1.0` | Restore `1.0`; the current adapter does not support speed adjustment |
| The model is neither Qwen3-TTS Base nor CustomVoice | Choose a supported model; changing the model name alone cannot add support for an arbitrary TTS model |

When the configuration actually changes, affected segments usually return to a state awaiting generation automatically. Run again and inspect `review`; segments still marked `FAILED` need `retry` to reset their attempt budget.

### Reference audio is missing, or a generated WAV was deleted or modified

These files have different purposes. Reference audio in `voices/` is input for future cloning; WAV files in `audio/` are generated results.

If a reference file is missing, prepare the recording again, put an existing file path in the corresponding voice in the complete cast, and reimport it. raradio copies the file and rechecks affected segments. Do not only edit a database path or overwrite a reference file named by its hash with a different file.

If a completed WAV is missing or its contents have changed, a normal `run` checks cache hashes and regenerates segments whose cached files are no longer valid. If the segment was already in the review queue, explicitly `retry` it and then `run`. `status` summarizes stored state; querying it does not repair files on disk. Export also revalidates audio and refuses to produce a finished book with missing audio.

### MLX, model loading, or project lock problems

If MLX-Audio is reported as uninstalled, run `sh setup.sh mlx`. If it is installed but cannot initialize, check that you are on Apple Silicon and that the process can access a Metal GPU. After fixing the runtime environment, restart the command and `retry` failed segments. Initialization failures are remembered within a process, so repeatedly trying again in that same process is not suitable.

If a model repository or local path does not exist, correct `model` or prepare the complete model files while online. Repeating generation offline will not fill in a missing cache.

If raradio reports that another process is modifying the project, find and stop the old generation command for that project before starting a new one. Only one process may write to a book at a time. Do not delete `.write.lock` to bypass a process that is still running.

### Restart a segment after repeated failures

Each segment gets up to 3 attempts by default, using `seed`, `seed + 1`, and `seed + 2`, with the actual seed recorded. A normal `run` does not retry `FAILED` or `NEEDS_REVIEW` segments indefinitely.

After you fix the cause, `retry` clears the segment's current generation state and resets its attempt count; synthesis happens on the next `run`. It does not reanalyze successfully annotated text or randomly select a different character. For a different set of random attempts, change `seed` in the complete voice configuration. This also affects other segments using that voice.

## Run a whole book, stop, resume, and make another version

After approving the short sample, run:

```sh
sh run.sh run work/my-book
```

To pause, press Ctrl+C in the running terminal and wait for the command to exit. Run the same `run` command next time to resume: valid completed audio is skipped, and unfinished generation is scheduled again. Segments that exhausted automatic retries still need their causes addressed and a `retry`. Stopping once does not require another `init`, analysis of the entire book, or reimport of the cast.

`build` combines import, optional configuration, analysis, generation, and optional export. It is convenient for short examples with known configurations. If the working directory already exists, it checks that the supplied TXT matches the saved source. Use `run` directly when continuing production on an existing book. After editing an external cast file, take care not to overwrite a project's newer configuration inadvertently with an old `build --cast` command.

Choose how to continue the same book:

| Need | Approach |
| --- | --- |
| Finish the current version or export it again | Keep the working directory, continue with `run`, and `export` when complete |
| Change one character's voice | Export the current complete cast to an editing file inside the working directory, change the relevant `voices` entry, reimport, and `run`; affected segments are regenerated and other valid audio is kept |
| Correct segment boundaries or chapter assignments | Export and review `structure`, then import the edited file; unaffected source spans retain their annotations and audio. See [structure repair](text-input.md) |
| Refresh automatic annotations | Use `analyze --reanalyze`; explicit human attributions remain intact |
| Revise the source text or compare an independent analysis | Create another `--work` directory from the TXT or settings; keep the original project for comparison |

After import, the source is fixed in `source.txt`, and its hash is checked when the project opens. To correct the input text, edit a TXT copy outside the project and import it into a new project. Directly editing `work/my-book/source.txt` breaks project consistency.

To use the same voices for your next book, reuse the `voices` configuration approach and reference recordings, but still discover and confirm the new book's own characters. Export the new book's discovered characters first, add the voice configurations you want to reuse to that complete table, and map each character again. raradio currently has no cross-book character library or automatic recognition that a character is the same person from a previous book.

Audio caches belong to a single working directory; reuse across books or new projects is not guaranteed. Changing voice configuration, reference audio, character attribution, or emotion changes the generation input for affected segments. A backend version change also triggers revalidation and generation. However, replacing weights in place under the same model ID or absolute path leaves the name unchanged, so the program cannot detect the new weights from that name alone. When comparing models, use model identifiers or directories that distinguish versions, and keep configuration records.

## Move the project to another machine

Stop generation normally before copying the book's whole working directory. Do not copy files separately while the database and audio are still being written.

```text
work/my-book/
├── source.txt
├── project.json
├── cast.json
├── state.sqlite3
├── voices/
├── audio/
└── .write.lock
```

You can copy the whole `work/my-book/` directory, including editing configurations or notes you have placed there. Copying only `output/my-book/` lets you keep listening, but does not let you restore segment state, change characters, or continue cloning.

On the other machine:

1. Prepare the same version of the raradio source and install the appropriate dependencies from its root. Speech generation still requires a supported Apple Silicon / Metal environment.
2. Prepare the models you used before. The working directory contains neither `.venv`, Ollama models, nor the Hugging Face cache. Prepare them again or migrate them using their respective tools.
3. Place the book's working directory somewhere convenient, such as `work/my-book/` in the new installation.
4. Check `model` in `cast.json`. Repository IDs can still be used. Absolute model paths from the old machine must be changed to existing paths on the new machine by importing a complete cast. Reference audio inside the project uses relative paths and normally moves with the book.
5. Inspect the status, generate a small amount to verify the setup, and then continue the rest.

```sh
sh run.sh doctor --profile mlx
sh run.sh status work/my-book
sh run.sh run work/my-book --limit 3
sh run.sh review work/my-book
```

Keeping the same dependencies, configuration, and models helps reuse existing audio. Changing a model path is a configuration change and may cause relevant segments to be regenerated; backend version changes can do the same. A successful copy does not verify synthesis in the new environment. Listen to some newly generated samples before continuing production.

## Change text models, TTS models, and runtime backends

These control different stages; changing the wrong setting will not produce the intended effect:

| What you want to change | Where to change it | Effect on existing projects |
| --- | --- | --- |
| Character identification, dialogue attribution, and emotion annotations | Text analysis options such as `--model` and `--think` on `analyze` / `build` | Applies to segments not yet successfully analyzed; does not automatically overwrite all existing annotations |
| Speech quality, preset voice, and cloning workflow | `voices.<VOICE_ID>.model` in the cast and voice parameters supported by that model | Segments using that voice need regeneration |
| MLX, another local runtime, or a remote synthesis service | Currently the cast's `backend`; adding a new type also requires adapter code | Depends on the backend implementation and version; an arbitrary name will not make it run |

### Change the Ollama text model

First prepare the desired model in Ollama, then select its tag in the command. For example, to use `qwen3:8b`:

```sh
ollama pull qwen3:8b
sh run.sh analyze work/my-book --model qwen3:8b --think false \
  --timeout 300 --batch-size 12
```

This demonstrates the options; it is not an assessment of that model's character identification quality. The model must return complete annotations according to raradio's supplied JSON schema. Answering questions in a chat window does not show that this contract has been validated. If a model does not accept the `think` parameter, use `--think omit`. For models with graded thinking support, choose `low`, `medium`, or `high` according to their actual capabilities.

To change the service address, use `--ollama-url http://YOUR_HOST:11434`. This changes only the analysis service location; TTS still runs through the backend in the cast. Using another host sends the text to that service. The default local address analyzes it on your machine.

By default, `analyze` processes only segments not yet successfully analyzed, while `retry` resets only generation. Add `--reanalyze` to refresh automatic annotations in the current project while preserving explicit human attributions. Review the resulting changes before continuing synthesis; failed or interrupted reanalysis blocks stale audio from export. For an independent comparison of two text models without prior manual decisions, create a new working directory for each from the same input. See [analysis and review](text-input.md).

### Change the TTS model

Export the current complete cast, change the voice's `model`, check the accompanying fields, import it, and generate a small amount first:

```sh
sh run.sh cast work/my-book > work/my-book/cast.edit.json
```

After editing `work/my-book/cast.edit.json`:

```sh
sh run.sh cast work/my-book --file work/my-book/cast.edit.json
sh run.sh run work/my-book --limit 3
sh run.sh segments work/my-book
```

The current `mlx` adapter supports only Qwen3-TTS Base and CustomVoice, and requires 24 kHz model output. Do not assume other model types are integrated just because they belong to Qwen3-TTS. When changing model size or quantization, still check the actual configuration type, supported languages, preset voices, or encoder capabilities.

When switching from Base to CustomVoice, remove `reference_audio`, `reference_text`, and `clone_mode`, set a supported `speaker`, and use strict. When switching in the other direction, prepare reference audio, explicitly set `clone_mode` to `icl` or `xvector`, and remove the preset `speaker` and `instruct`. ICL also needs an accurate transcript; xvector omits it. Keep `speed` at `1.0` for both routes. raradio rejects unsupported capabilities instead of silently treating invalid fields as effective.

### Change the runtime backend or customize the code

The only supported backend names are currently `tone` and `mlx`. `tone` is for diagnostics; `mlx` generates the current real speech output. Integrating another library, service, or non-Qwen TTS requires implementing and registering a backend. Merely changing `backend` in JSON to a new name is not enough.

For example, llama.cpp has a GGUF route for Qwen3-TTS Base, but its TTS tooling is still experimental and is not integrated into raradio. For independent verification steps and its relationship to Ollama and MLX, see the [backend strategy](backend-strategy.md). The production commands in this handbook continue to use integrated backends.

Start development with the [backend implementation](../raradio/backends.py), [data contracts](../raradio/models.py), and [architecture](architecture.md). A backend receives the original text, voice configuration, emotion, and target file path, produces a PCM16 WAV that can be checked, and supplies a version identifier. Custom backends should explicitly reject unsupported capabilities, preserve the original text, and let version changes invalidate old caches. See the [backend strategy](backend-strategy.md) for more detail on model and backend choices.

## Verification scope and reproduction

The repository supplies short TXT files, voice configuration templates, and automated tests. It does not distribute pregenerated listening samples or reference recordings for cloning. Scenario 1 checks the production workflow without downloading models; scenario 2 generates preset voice samples; scenario 4 tests xvector cloning once you supply your own reference audio. Generated results are saved in the working and export directories specified by each command.

Run the automated tests from the source root:

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -q
```

Tests cover segmentation, validation of analysis results, character confirmation, configuration import, cache invalidation, retries, export, and related behavior. MLX adapter tests use substitute models to check call parameters and audio processing; they do not measure real speech quality. Real ICL inference and listening evaluation have not yet been completed, so passing contract tests must not be treated as verification of voice quality.

The project's recorded CustomVoice and Base xvector short-sample runs check only model interfaces and the workflow. Neither short samples nor waveform checks establish whole-book stability, character identification accuracy, word-for-word pronunciation, clone similarity, or emotional expression. With any new model, recording, or runtime environment, you still need to generate representative samples and listen.

ASR checks against the source text, voice identity checks, EPUB import, MP3/M4B export, and a complete graphical review interface are not yet implemented. See [verification](verification.md) for test scope and reproduction steps, and the [plan](plan.md) for implementation directions.

## Current extensions and possible future plugins

Model runtimes may have their own model types, loaders, or plugin mechanisms. Those capabilities do not automatically mean raradio has integrated the corresponding workflows. raradio currently extends through analyzers and backend adapters in code. It has no plugin marketplace or plugin registry for installing, discovering, and registering third-party backends.

Choosing a compatible model usually starts with configuration changes. Moving between runtimes or model families requires adapter code and verification with real samples. Any future plugin registry must explicitly describe supported cloning modes, reference transcripts, emotion, languages, and output formats. See the [backend strategy](backend-strategy.md) for the distinction between currently available capabilities and future options.
