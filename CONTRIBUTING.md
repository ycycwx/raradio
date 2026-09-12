# Contributing

English | [简体中文](CONTRIBUTING.zh-CN.md)

Contributions to raradio's workflow, backend adapters, documentation, and evaluation are welcome. The project is in Alpha. For changes to the project file format, state machine, or public interfaces, first describe the use case and migration impact.

## Development environment

Core development requires Python 3.11+ and a POSIX system providing `fcntl`. After obtaining the source, run this from the repository root:

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

Tests use only the standard library and need no Ollama, MLX, or model weights. Real speech verification requires an Apple Silicon Mac; see the [handbook](docs/handbook.md) for setup. `sh setup.sh core` synchronizes the virtual environment to the core dependencies; use `sh setup.sh mlx` to retain speech support in the environment.

## Principles for changes

- Keep source text unchanged after import. Store character, emotion, voice configuration, and manual review results separately.
- Add tests that expose the issue for behavior changes. For model-related work, verify the adapter contract first, then use a short sample to check real behavior.
- New backends should declare their supported parameters and output formats, reject unsupported capabilities, and provide a version identifier that participates in caching.
- The core manages project writes, bounded retries, and cache rules; avoid duplicating the entire workflow in each backend.
- Keep the complete workflow usable without a UI or interactive prompt. Preserve JSON output, exit codes, and path behavior for callers; simplify common tasks without hiding configuration or silently selecting different voices.
- Documentation must distinguish implemented capabilities, capabilities tested in practice, and planned work. A successful short sample is not a guarantee of quality for a whole book.

See [architecture](docs/architecture.md) for module responsibilities and [backend strategy](docs/backend-strategy.md) for backend direction. There is currently no stable third-party plugin SDK; adding a backend requires changing internal registration points.

## Language conventions

English is the canonical public entry point. The default Markdown files use English; their `.zh-CN.md` counterparts provide complete Simplified Chinese documentation. Keep both versions in sync when changing behavior, instructions, or examples, including language switches, relative links, and section links.

Use English for code comments and documentation strings, CLI help and messages, and the default issue templates and issue language. Preserve identifiers, configuration keys, commands, model IDs, and operational values when translating documentation.

Documentation language is independent of the language being synthesized. Keep source texts, dialogue examples, and reference transcripts in their original language; do not translate them mechanically to match the documentation. In particular, `reference_text` must transcribe what the recording actually says, and a synthesis `language` setting must match the intended output. The supplied Chinese examples remain Chinese in both documentation versions.

## Reporting issues

Provide the raradio version or commit, system and Python versions, relevant dependency and model versions, reproduction command, expected behavior, and actual result. Prefer reproducing with the original short texts in `examples/` or a new minimal text, and include the relevant segments' status and error messages.

Remove paths containing usernames, service credentials, and private addresses before sharing logs. Do not upload entire books, complete working directories, model weights, or reference recordings you are not authorized to share. `doctor` output can help with diagnosis, but inspect its tool paths and model list before sharing it too.

## Before submitting

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
sh -n setup.sh run.sh
git diff --check
git status --short
```

A PR description should cover the changed behavior, how it was verified, and platforms or models that remain unverified. When updating documentation, check relative links, JSON examples, and command prerequisites. Every example should be reproducible from the obtained source and explicitly listed inputs.

`tests/test_examples.py` runs the public offline teaching script. `tests/test_example_templates.py` uses the public TXT files and cast templates to verify import, synthesis contracts, chapter export, and caching. When editing examples, retain all four parts: preparation, manual steps, actual commands, and expected output. Checking that JSON parses is not enough. Reference recordings for clone templates are generated temporarily during tests, and model inference is substituted; this does not establish cloning quality.

GitHub Actions checks the locked core source environment on macOS/Linux with Python 3.11–3.14. A manually selected MLX job checks optional dependency installation and consistency on Apple Silicon; it downloads no models and does not verify speech quality. See [maintenance](docs/maintenance.md) for dependency updates, version policy, and source-update checks.

Keep personal inputs, reference recordings, and temporary configuration in the ignored `work/`, `output/`, or `configs/` directories. Generated media, model files, and credentials are not committed by default. If public test assets are needed, first establish their source and license, then deliberately adjust the ignore and packaging rules.

## License

raradio's own code, documentation, and original examples use [MIT](LICENSE). You must have the right to distribute your contributions under that license. Clearly identify the source and original license of third-party materials; raradio's license must not replace theirs.

## Agent-facing behavior

The production Skill lives at `raradio/skills/raradio-audiobook/SKILL.md` in the repository. `sh run.sh agent-guide` exposes it through the source CLI; keep command examples and state/review rules aligned with CLI changes. Maintain the workflow in this single portable English Skill and keep its short entry in both READMEs in sync. Do not duplicate the Skill in separate guides or client-specific directories in the repository. Root `AGENTS.md` contains repository development instructions.

Validate discovery with `python3 -m unittest tests.test_agent_guide -v`. Significant workflow changes should also be exercised by an agent reading only the bundled guide on original short inputs. Record tone-only checks separately from real speech or listening results.
