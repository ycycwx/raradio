# Install raradio

English | [简体中文](installation.zh-CN.md)

The supported installation path is a GitHub source checkout. For most people the shortest route is: prepare the speech environment, run the setup check, then make a short single-voice sample. Ollama is optional and is only needed for raradio's built-in automatic multi-character analysis.

## Before you start

Real speech currently requires an Apple Silicon Mac with macOS 14 or later and Metal access. You also need network access for Python packages and the first TTS model download. Native Windows and Intel Macs are not supported for speech generation yet.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). uv prepares the requested Python version and an isolated `.venv` inside the checkout; it is not a raradio runtime service.

## Install from GitHub

```sh
git clone https://github.com/ycycwx/raradio.git
cd raradio
sh setup.sh mlx
sh run.sh setup
```

`setup.sh mlx` installs the locked Python 3.11 speech dependencies into `.venv`. `sh run.sh setup` is a read-only explanation and verification step; it does not install software or download models. Keep using `sh run.sh ...` from the repository root, or `sh /path/to/raradio/run.sh ...` elsewhere.

To update later, preserve any work directories and local configuration, update the checkout, then rerun `sh setup.sh mlx`. Review the changelog before using a newer Alpha revision with an existing book project.

## Make a first single-voice sample

From the repository root, run the supplied short example first:

```sh
sh run.sh build examples/clone.txt --work work/single \
  --analyzer single-voice --cast examples/cast.single.json --limit 3
```

The first synthesis downloads the selected model from Hugging Face and can take longer; later runs reuse the cache. An intentional limited run exits with status `2` while work remains. Listen to the WAV files in `work/single/audio/`. If the voice is suitable, finish and export:

```sh
sh run.sh run work/single
sh run.sh export work/single --output output/single
```

This path does not install or contact Ollama. Keep `work/single/` so you can resume, correct a segment, or change the voice without starting over. For your own book, copy and edit `examples/cast.single.json`, then replace the example text and paths in the command.

## Add automatic multi-character analysis only if needed

Install and start [Ollama](https://ollama.com/download), then prepare the default text model and check both services:

```sh
ollama pull qwen3:14b
sh run.sh setup --mode multi-voice --model qwen3:14b
```

Ollama identifies likely characters, speakers, and emotions; it does not generate speech. You still need to review the cast and uncertain lines. If your existing terminal agent is doing the attribution, it can read `sh run.sh agent-guide` and skip Ollama.

## What each download is for

| Item | When it is needed | How it arrives |
| --- | --- | --- |
| raradio source and CLI | Always | Cloned from GitHub; the CLI runs through `sh run.sh` |
| Python and MLX-Audio runtime | Real speech | Installed into `.venv` by `sh setup.sh mlx` |
| TTS model weights | First real speech generation | Downloaded from Hugging Face and then cached |
| Ollama application and text model | Only built-in multi-character analysis | Installed and downloaded separately through Ollama |

`sh run.sh setup` checks dependencies but does not initialize Metal, generate speech, judge voice quality, or prove that model weights are already cached. For the full production workflow and troubleshooting, continue with the [handbook](handbook.md).
