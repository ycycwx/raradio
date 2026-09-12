#!/bin/sh
set -eu
cd "$(dirname "$0")"
profile="${1:-core}"
case "$profile" in
  -h|--help) echo 'Usage: sh setup.sh [core|mlx]'; exit 0 ;;
  core|mlx) ;;
  *) echo 'Usage: sh setup.sh [core|mlx]' >&2; exit 1 ;;
esac
if [ "$#" -gt 1 ]; then
  echo 'Usage: sh setup.sh [core|mlx]' >&2
  exit 1
fi
if [ "$profile" = mlx ]; then
  if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
    echo 'The MLX backend requires an Apple Silicon Mac with macOS 14 or newer.' >&2
    exit 1
  fi
  macos_version="$(sw_vers -productVersion)"
  if [ "${macos_version%%.*}" -lt 14 ]; then
    echo 'The locked MLX packages require macOS 14 or newer. Use core for the model-free workflow.' >&2
    exit 1
  fi
fi
if ! command -v uv >/dev/null 2>&1; then
  echo 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2
  exit 1
fi
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.uv-cache}"
# The checkout wrappers share one environment, regardless of inherited uv settings.
export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
case "$profile" in
  core) uv sync --locked ;;
  mlx) uv sync --locked --extra mlx ;;
esac
.venv/bin/raradio doctor --profile "$profile"
