#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 CASE_ID" >&2
  exit 2
fi
CASE="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
STATE_FILE="$ROOT/evidence/active/$CASE.json"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE_OUT="$ROOT/evidence/${CASE}__verifier_evidence__${STAMP}.json"
UV_RUN=(uv run --no-project --python "$VENV/bin/python")

command -v uv >/dev/null 2>&1 || { echo "uv is required but was not found on PATH" >&2; exit 2; }
[[ -x "$VENV/bin/python" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }
[[ -f "$STATE_FILE" ]] || { echo "Run ./scripts/prepare_case.sh $CASE first" >&2; exit 2; }
WORK="$("${UV_RUN[@]}" python - "$STATE_FILE" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["workspace"])
PY
)"

# Keep a stable copy in the experiment evidence directory.
(
  cd "$ROOT"
  "${UV_RUN[@]}" python "$ROOT/benchmark/verifier_evidence.py" "$WORK" "$ARCHIVE_OUT"
)

# Also expose the same report inside the workspace for the verifier agent, but
# exclude this harness-only directory from git status/diff so it is never
# mistaken for an agent repair artifact by the evaluator.
mkdir -p "$WORK/.driftguard"
printf '%s\n' '.driftguard/' >> "$WORK/.git/info/exclude"
cp "$ARCHIVE_OUT" "$WORK/.driftguard/verifier_evidence.json"

cat <<MSG
Verifier evidence archived at: $ARCHIVE_OUT
Verifier-visible copy: $WORK/.driftguard/verifier_evidence.json

Give the verifier agent ONLY the blinded workspace plus prompts/verifier_agent.md.
The .driftguard directory is harness metadata and is excluded from repair diffs.
MSG
