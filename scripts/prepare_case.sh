#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 CASE_ID" >&2
  exit 2
fi

CASE="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor/jaffle_shop_duckdb"
VENV="$ROOT/.venv"
WORK="$ROOT/workspaces/$CASE"
CASEFILE="$ROOT/benchmark/cases/$CASE.json"
BASEFILE="$ROOT/evidence/bases/$CASE.txt"
UV_RUN=(uv run --no-project --python "$VENV/bin/python")

command -v uv >/dev/null 2>&1 || { echo "uv is required but was not found on PATH" >&2; exit 2; }
[[ -x "$VENV/bin/python" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }
[[ -f "$CASEFILE" ]] || { echo "Unknown case: $CASE" >&2; exit 2; }
[[ -d "$VENDOR/.git" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }

rm -rf "$WORK"
git clone --local "$VENDOR" "$WORK" >/dev/null

git -C "$WORK" config user.email "benchmark@driftguard.local"
git -C "$WORK" config user.name "DriftGuard Benchmark"

"${UV_RUN[@]}" python "$ROOT/benchmark/apply_incident.py" "$CASE" "$WORK"

git -C "$WORK" add -A
git -C "$WORK" commit -m "Inject DriftGuard incident: $CASE" >/dev/null
mkdir -p "$(dirname "$BASEFILE")"
git -C "$WORK" rev-parse HEAD > "$BASEFILE"

cat <<MSG
Prepared: $WORK
Incident is committed as the workspace baseline.
Give this directory to the agent. Evaluate afterward with:
  ./scripts/evaluate_case.sh $CASE baseline
MSG
