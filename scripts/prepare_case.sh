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
CASEFILE="$ROOT/benchmark/cases/$CASE.json"
STATE_DIR="$ROOT/evidence/active"
STATE_FILE="$STATE_DIR/$CASE.json"
UV_RUN=(uv run --no-project --python "$VENV/bin/python")

command -v uv >/dev/null 2>&1 || { echo "uv is required but was not found on PATH" >&2; exit 2; }
[[ -x "$VENV/bin/python" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }
[[ -f "$CASEFILE" ]] || { echo "Unknown case: $CASE" >&2; exit 2; }
[[ -d "$VENDOR/.git" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }

# Do not leak the incident name through the workspace path. The random run id is
# recorded outside the agent workspace and resolved later by evaluate_case.sh.
RUN_ID="run_$("${UV_RUN[@]}" python - <<'PY'
import secrets
print(secrets.token_hex(6))
PY
)"
WORK="$ROOT/workspaces/$RUN_ID"
rm -rf "$WORK"
mkdir -p "$ROOT/workspaces" "$STATE_DIR"

git clone --no-hardlinks "$VENDOR" "$WORK" >/dev/null

git -C "$WORK" config user.email "sync@upstream.local"
git -C "$WORK" config user.name "Upstream Sync"

"${UV_RUN[@]}" python "$ROOT/benchmark/apply_incident.py" "$CASE" "$WORK" >/dev/null

git -C "$WORK" add -A
# Keep the commit realistic and blind: neither the case id nor mutation type is exposed.
git -C "$WORK" commit -m "Sync upstream source snapshot" >/dev/null
BASE="$(git -C "$WORK" rev-parse HEAD)"

"${UV_RUN[@]}" python - "$STATE_FILE" "$CASE" "$RUN_ID" "$WORK" "$BASE" <<'PY'
import json, pathlib, sys
out, case, run_id, work, base = sys.argv[1:]
p = pathlib.Path(out)
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"case": case, "run_id": run_id, "workspace": work, "base": base}, indent=2) + "\n")
PY

cat <<MSG
Prepared blinded workspace: $WORK
Run id: $RUN_ID
Incident metadata is intentionally kept outside the workspace.
Give ONLY this workspace directory to the agent.
Evaluate afterward with:
  ./scripts/evaluate_case.sh $CASE baseline
MSG
