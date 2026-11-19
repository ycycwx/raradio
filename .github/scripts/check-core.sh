#!/bin/sh
set -eu

uv lock --check
sh setup.sh core
actual_version=$(.venv/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])')
if [ "$actual_version" != "$UV_PYTHON" ]; then
  echo "Expected Python $UV_PYTHON, found $actual_version in .venv" >&2
  exit 1
fi
uv pip check --python .venv/bin/python
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests -v
sh -n setup.sh
sh -n run.sh
