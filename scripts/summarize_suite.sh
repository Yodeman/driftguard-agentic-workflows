#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 2; }
[[ -x "$VENV/bin/python" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }
uv run --no-project --python "$VENV/bin/python" python "$ROOT/benchmark/aggregate_runs.py" "$@"
