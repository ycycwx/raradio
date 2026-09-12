#!/bin/sh
set -eu
RARADIO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -x "$RARADIO_ROOT/.venv/bin/raradio" ]; then
  echo "Run sh \"$RARADIO_ROOT/setup.sh\" core (diagnostic) or mlx (speech) first." >&2
  exit 1
fi
exec "$RARADIO_ROOT/.venv/bin/raradio" "$@"
