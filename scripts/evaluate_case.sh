#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 CASE_ID [SYSTEM_NAME]" >&2
  exit 2
fi

CASE="$1"
SYSTEM="${2:-unspecified}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
WORK="$ROOT/workspaces/$CASE"
BASEFILE="$ROOT/evidence/bases/$CASE.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/evidence/${CASE}__${SYSTEM}__${STAMP}.json"
UV_RUN=(uv run --no-project --python "$VENV/bin/python")

command -v uv >/dev/null 2>&1 || { echo "uv is required but was not found on PATH" >&2; exit 2; }
[[ -x "$VENV/bin/python" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }
[[ -d "$WORK/.git" ]] || { echo "Workspace missing. Run ./scripts/prepare_case.sh $CASE" >&2; exit 2; }
[[ -f "$BASEFILE" ]] || { echo "Incident baseline missing. Re-run ./scripts/prepare_case.sh $CASE" >&2; exit 2; }
BASE="$(cat "$BASEFILE")"

set +e
"${UV_RUN[@]}" python "$ROOT/benchmark/evaluate.py" \
  "$CASE" "$WORK" --system "$SYSTEM" --base "$BASE" --output "$OUT"
STATUS=$?
set -e

"${UV_RUN[@]}" python - "$OUT" "$ROOT/evidence/results.jsonl" <<'PY'
import json, pathlib, sys
src, dst = map(pathlib.Path, sys.argv[1:])
payload = json.loads(src.read_text())
with dst.open("a") as f:
    f.write(json.dumps(payload, sort_keys=True) + "\n")
PY

echo "Saved result: $OUT"
exit "$STATUS"
