# Dependencies, Versions, and Source Updates

English | [简体中文](maintenance.zh-CN.md)

raradio is currently distributed as a GitHub source checkout. It has a small standard-library core and an optional speech stack. See the [installation guide](installation.md) for the supported user path.

## For developers coming from JavaScript

| File or tool | Role in raradio | Rough JavaScript analogy |
| --- | --- | --- |
| `pyproject.toml` | Project metadata, supported Python, direct dependencies, CLI entry point, and local build configuration | `package.json` |
| `uv.lock` | Exact resolved Python packages, platform markers, and artifact hashes | `pnpm-lock.yaml` |
| `.python-version` | Default Python minor version for a source checkout: 3.11 | `.nvmrc` |
| `uv sync --locked` | Create/update `.venv` using the committed resolution; fail if the lock needs changing | Frozen-lockfile install |
| `.venv` | Isolated Python interpreter and installed packages; never commit it | Per-project runtime environment |
| `uv` | Project, Python, environment, and dependency manager used by the checkout | pnpm plus a Python/version manager |

`pyproject.toml` remains necessary for source-only use: uv reads it to install the project, expose the `raradio` command in `.venv`, and select the optional `mlx` dependencies. uv downloads Python dependencies from public indexes, but raradio itself is obtained from GitHub.

## Installation contract

- Core has no third-party Python runtime dependencies. It needs Python 3.11+ and POSIX locking (`fcntl`); native Windows is not supported.
- Real speech uses `mlx-audio[tts]==0.5.3` on native Apple Silicon macOS. The locked environment requires macOS 14 or newer and recommends Python 3.11.
- `sh setup.sh mlx` checks the platform before resolving packages and installs the locked environment. `sh setup.sh core` prepares only the model-free workflow.
- Model weights are separate downloads and are not stored in the repository or lockfile. GPU/Metal access and sufficient memory still matter after dependency installation.
- Ollama is optional and only used when selected for analysis. FFmpeg is optional for the existing PCM16 mono WAV workflow.

The lockfile contains public dependency URLs and optional resolutions. Do not commit personal registry URLs, credentials, local paths, or a machine's complete `pip freeze` output. Keep project data (`work/`) separate from `.venv`; rebuilding the environment must not rebuild a book.

## Updating dependencies

Update one direct dependency at a time when possible:

```sh
uv lock --upgrade-package PACKAGE --index-url https://pypi.org/simple
uv lock --check
sh setup.sh core
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests -v
```

To change the pinned `mlx-audio` version, first update `pyproject.toml`, then regenerate the lock. Review the adapter, upstream compatibility, and licenses. For speech changes, also run `sh setup.sh mlx`, `uv pip check`, and the short real-model checks in [verification](verification.md).

Dependabot proposes monthly updates for GitHub Actions and the uv ecosystem; it does not merge changes or publish anything automatically.

## Version and project-format policy

`raradio/__init__.py::__version__` is the single authored application version. The CLI reports it, and the uv cache key includes the file. Use `0.MINOR.PATCH` during Alpha: compatible fixes increment patch; intentional CLI, JSON, cast, or project-format breaks increment minor and require explicit notes.

Book projects have their own `schema_version`. raradio rejects unsupported schemas and has no automatic migration yet. Before changing the schema, provide an explicit migration path or state that users need a new work directory. Back up an existing project before trying a newer Alpha revision.

## Source update checklist

1. Update both changelogs for behavior, schema, dependency, model, or platform changes.
2. Run `uv lock --check`, all model-free tests, shell syntax checks, and `git diff --check`.
3. Run the public model-free example from a clean checkout. If speech code changed, separately verify a short real sample on supported hardware.
4. Inspect tracked files for credentials, personal paths, books, recordings, model weights, generated audio, databases, and environments.
5. Create a Git tag or GitHub Release only after the exact commit has passed the intended checks. No package registry publication is part of this process.

The current changelog is **Unreleased**. Keep planned CI coverage separate from recorded local or hosted evidence.
