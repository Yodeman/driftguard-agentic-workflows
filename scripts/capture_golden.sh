#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor/jaffle_shop_duckdb"
VENV="$ROOT/.venv"
WORK="$ROOT/workspaces/_golden"
UV_RUN=(uv run --no-project --python "$VENV/bin/python")

command -v uv >/dev/null 2>&1 || { echo "uv is required but was not found on PATH" >&2; exit 2; }
[[ -x "$VENV/bin/python" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }
[[ -d "$VENDOR/.git" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }

rm -rf "$WORK"
git clone --local "$VENDOR" "$WORK" >/dev/null

(
  cd "$WORK"
  "${UV_RUN[@]}" dbt build --profiles-dir .
)

"${UV_RUN[@]}" python "$ROOT/benchmark/snapshot.py" \
  "$WORK/jaffle_shop.duckdb" \
  "$ROOT/evidence/golden_snapshot.json"

echo "Golden semantic snapshot captured."
