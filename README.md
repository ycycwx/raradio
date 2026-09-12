# raradio

English | [简体中文](https://github.com/ycycwx/raradio/blob/main/README.zh-CN.md)

**A headless CLI for turning TXT files into audiobooks you can revise and resume.** Choose one narrator or an explicitly reviewed cast, generate audio segment by segment, and export chapter WAV files and SRT subtitles. Commands and JSON files are the primary interface.

**Alpha · Real speech currently requires an Apple Silicon Mac.** The model-free workflow also runs without speech dependencies. Long-book quality and additional speech backends are still being evaluated.

raradio is for people who prefer terminals and automation. Its goal is an audiobook production tool that is easy to install, easy to revise, and straightforward to script.

- **Simple to start:** check the complete workflow without models; use one narrator without an analysis service.
- **Predictable to use:** preserve the source, save progress per segment, reuse valid audio, and collect exceptions for review.
- **Flexible to automate:** separate import, analysis, casting, generation, and export; use JSON results and explicit exit codes in scripts.
- **Work with your agent:** let your existing terminal agent configure casting, confirm clear attributions and apply feedback through the CLI; use the [bundled Skill](https://github.com/ycycwx/raradio/blob/main/raradio/skills/raradio-audiobook/SKILL.md) to teach the workflow.
- **Open to extend:** keep analysis and speech adapters separate from the project state. These are internal interfaces today; a stable plugin SDK is still future work.

A UI could later consume the same workflow. Building or requiring one is not this project's primary goal. Headless means no graphical interface or interactive prompt is required; it does not remove decisions about voices or the need to listen to samples.

[Installation](https://github.com/ycycwx/raradio/blob/main/docs/installation.md) · [Handbook](https://github.com/ycycwx/raradio/blob/main/docs/handbook.md) · [Manuscript formats](https://github.com/ycycwx/raradio/blob/main/docs/text-input.md) · [Examples](https://github.com/ycycwx/raradio/blob/main/examples/README.md) · [Similar projects](https://github.com/ycycwx/raradio/blob/main/docs/reference-projects.md) · [Maintenance](https://github.com/ycycwx/raradio/blob/main/docs/maintenance.md) · [Contributing](https://github.com/ycycwx/raradio/blob/main/CONTRIBUTING.md)

English is the default documentation language; each page links to its Simplified Chinese version. Documentation language and speech synthesis language are independent; the supplied Chinese examples remain Chinese.

## Install and start

Real speech currently requires an Apple Silicon Mac with macOS 14+ and Metal access. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), clone the repository, and run:

```sh
git clone https://github.com/ycycwx/raradio.git
cd raradio
sh setup.sh mlx
sh run.sh setup
```

Start with `single-voice`: it reads narration and dialogue with one voice and **does not need Ollama**. The TTS model downloads from Hugging Face on the first speech generation and is cached afterward. Add Ollama only if you want raradio's built-in automatic multi-character analysis:

```sh
sh run.sh setup --mode multi-voice
```

`sh run.sh setup` checks and explains prerequisites; it never installs software or downloads models. The repository checkout is currently the only supported distribution and installation path.

Follow the [installation guide](https://github.com/ycycwx/raradio/blob/main/docs/installation.md) for the first single-voice sample, downloads, updates, and Ollama setup. To verify the complete workflow without speech models, use the [model-free example](https://github.com/ycycwx/raradio/blob/main/examples/README.md#demo-model-free-end-to-end-smoke-test).

## Use with your existing agent

The bundled [raradio-audiobook Skill](https://github.com/ycycwx/raradio/blob/main/raradio/skills/raradio-audiobook/SKILL.md) teaches a terminal-capable agent how to prepare, generate and revise a book. Agent-led attribution can skip Ollama; real speech still needs the TTS environment. For example, ask your agent:

> Read `sh run.sh agent-guide`, then help me turn `book.txt` into an audiobook. Configure the voices and generate a short sample first. You may decide clear speaker attributions; leave ambiguities for me to confirm.

The source CLI prints the complete Skill:

```sh
sh run.sh agent-guide
```

For Skill discovery, save the command's output in your client's documented skill directory, for example `.agents/skills/raradio-audiobook/SKILL.md`. Review any existing custom copy before replacing it, and refresh it when updating raradio. Preparing the source environment does not register the Skill with your agent automatically.

## Use cloned voices or a full cast

| Scenario | Configuration template | What to prepare |
| --- | --- | --- |
| Single preset narrator | [cast.single.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.single.json) | CustomVoice model |
| Clone from a reference recording only | [cast.clone.xvector.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.clone.xvector.json) | Base model and a clear recording of one speaker |
| Clone from a recording and transcript | [cast.clone.icl.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.clone.icl.json) | Base model, recording, accurate transcript, and a compatible encoder |
| Multiple preset voices | [cast.mlx.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.mlx.json) | Ollama and a CustomVoice model |
| Mix cloned and preset voices | [cast.mixed.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.mixed.json) | Ollama, both types of TTS model, and a reference recording |

Copy a template and prepare the inputs following the [example instructions](https://github.com/ycycwx/raradio/blob/main/examples/README.md). Supply your own `reference.wav` for templates that use it, and replace the ICL transcript placeholder. Relative reference audio paths are resolved from the JSON file's directory; the recording is copied into the book project on import.

A short story with multiple characters:

```sh
ollama pull qwen3:14b
sh run.sh doctor --profile ollama --model qwen3:14b
sh run.sh build examples/story.txt --work work/story \
  --cast examples/cast.mlx.json --output output/story
```

Before running, install and start Ollama and run `sh setup.sh mlx`. The example cast is specific to the supplied short story. For your own fiction, analyze it first, then edit the complete discovered cast. See the [handbook](https://github.com/ycycwx/raradio/blob/main/docs/handbook.md) for the steps and which decisions are manual or automatic.

## Working directories and everyday commands

`work/my-book/` stores the source text, cast configuration, reference audio, SQLite state, and per-segment WAV files; `output/my-book/` holds the exported files. Keep the entire working directory to resume production or change voices.

```sh
sh run.sh status work/story
sh run.sh review work/story
sh run.sh run work/story
sh run.sh export work/story --output output/story
```

Importing a cast with `cast --file` **replaces the entire table**, so retain the other characters when editing. Changing the analyzer or text model does not automatically redo successful annotations; use a new working directory to compare analysis approaches. Changing a voice configuration causes the affected audio to be regenerated.

Workflow JSON results go to stdout; progress and errors go to stderr. Help, version output, `setup`, and `agent-guide` use text; the latter two also accept `--format json`. When `build` / `run` returns valid JSON, exit code `0` means everything is complete and `2` means work remains, possibly just because `--limit` was reached. Argument parsing errors can also return `2`, but without a JSON result. Errors caught during execution return `1`; interruption returns `130`.

`raradio`, `python -m raradio`, and `sh /path/to/run.sh` resolve relative command arguments from your current directory. Reference audio paths in cast JSON remain relative to the JSON file. Examples on this page assume you are in the repository root.

## Scope

Currently supported: TXT input, chapter WAV files, segment-level SRT subtitles, waveform checks, and manual review. EPUB, MP3/M4B, ASR readback, voice similarity checks, and automatic discovery of third-party plugins are not yet implemented. This is not yet a general CPU/CUDA/Linux speech tool or a polished one-click ebook converter. Automatic character analysis still needs cast confirmation and uncertain lines need manual review; a successful audio check cannot detect misread words or inconsistent voices.

llama.cpp is a candidate backend and is not currently integrated. See the [backend strategy](https://github.com/ycycwx/raradio/blob/main/docs/backend-strategy.md) for interfaces, implemented capabilities, and the integration order. See [testing and verification](https://github.com/ycycwx/raradio/blob/main/docs/verification.md) for execution evidence and reproduction steps.

## Development and licensing

Tests do not require model downloads:

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

For version changes, dependency updates, project-format compatibility, and source-update checks, see [maintenance](https://github.com/ycycwx/raradio/blob/main/docs/maintenance.md) and the [changelog](https://github.com/ycycwx/raradio/blob/main/CHANGELOG.md). The [open-source review](https://github.com/ycycwx/raradio/blob/main/docs/open-source-review.md) records current gaps and follow-up priorities.

Read the [contribution guide](https://github.com/ycycwx/raradio/blob/main/CONTRIBUTING.md) before reporting an issue or submitting a change. Use original short texts and configurations that can be shared publicly for reproductions; avoid including personal books, recordings, or credentials.

raradio's own code, documentation, and original examples use the [MIT license](https://github.com/ycycwx/raradio/blob/main/LICENSE). Dependencies, model weights, and user inputs retain their respective licenses. See the [third-party notice](https://github.com/ycycwx/raradio/blob/main/THIRD_PARTY.md) for the scope and components that need separate treatment.
