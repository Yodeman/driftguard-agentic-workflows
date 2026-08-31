#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 CASE_ID" >&2
  exit 2
fi

CASE="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
OPENCODE_BIN="${DRIFTGUARD_OPENCODE_BIN:-opencode}"
MODEL="${DRIFTGUARD_OPENCODE_MODEL:-}"
VARIANT="${DRIFTGUARD_OPENCODE_VARIANT:-max}"
AGENT="${DRIFTGUARD_OPENCODE_AGENT:-build}"
STATE_FILE="$ROOT/evidence/active/$CASE.json"
TRACE_PY="$ROOT/benchmark/opencode_trace.py"

command -v "$OPENCODE_BIN" >/dev/null 2>&1 || { echo "OpenCode CLI not found" >&2; exit 2; }
command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 2; }
[[ -x "$VENV/bin/python" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }
[[ -f "$ROOT/evidence/golden_snapshot.json" ]] || { echo "Run ./scripts/capture_golden.sh first" >&2; exit 2; }
[[ -f "$ROOT/benchmark/cases/$CASE.json" ]] || { echo "Unknown case: $CASE" >&2; exit 2; }

strip_ansi() { sed -r 's/\x1B\[[0-9;]*[mK]//g'; }
if [[ -z "$MODEL" ]]; then
  mapfile -t matches < <(NO_COLOR=1 "$OPENCODE_BIN" models 2>/dev/null | strip_ansi | awk '{$1=$1;print}' | grep -Ei '(^|/)glm-5\.3-flash([[:space:]]|$)' | awk '{print $1}' | sort -u || true)
  [[ ${#matches[@]} -eq 1 ]] || { echo "Set DRIFTGUARD_OPENCODE_MODEL to an exact provider/model string." >&2; exit 2; }
  MODEL="${matches[0]}"
fi

"$ROOT/scripts/prepare_case.sh" "$CASE" >/dev/null
readarray -t STATE < <(uv run --no-project --python "$VENV/bin/python" python - "$STATE_FILE" <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); print(x['run_id']); print(x['workspace'])
PY
)
RUN_ID="${STATE[0]}"; WORK="${STATE[1]}"
OUT="$ROOT/evidence/baseline_only/$CASE/$RUN_ID"
mkdir -p "$OUT"
PROMPT="$(cat "$ROOT/prompts/baseline.md")"

set +e
(
  cd "$WORK"
  PATH="$VENV/bin:$PATH" VIRTUAL_ENV="$VENV" NO_COLOR=1 BROWSER=none \
    "$OPENCODE_BIN" run --model "$MODEL" --variant "$VARIANT" --format json --thinking \
      --agent "$AGENT" --dir "$WORK" --title "DriftGuard baseline-only $RUN_ID" "$PROMPT"
) >"$OUT/baseline.events.jsonl" 2>"$OUT/baseline.stderr.log"
AGENT_RC=$?
set -e
printf '%s\n' "$AGENT_RC" > "$OUT/baseline.exit_code"

SID="$(uv run --no-project --python "$VENV/bin/python" python "$TRACE_PY" session-id "$OUT/baseline.events.jsonl" 2>/dev/null || true)"
if [[ -n "$SID" ]]; then
  "$OPENCODE_BIN" export "$SID" >"$OUT/baseline.export.json" 2>"$OUT/baseline.export.stderr.log" || true
fi

ARGS=(python "$TRACE_PY" summarize "$OUT/baseline.events.jsonl" --output "$OUT/baseline.summary.json" --text-output "$OUT/baseline.final.txt")
[[ -f "$OUT/baseline.export.json" ]] && ARGS+=(--export "$OUT/baseline.export.json")
uv run --no-project --python "$VENV/bin/python" "${ARGS[@]}" >/dev/null

set +e
"$ROOT/scripts/evaluate_case.sh" "$CASE" baseline_submission
EVAL_RC=$?
set -e
LATEST="$(ls -1t "$ROOT/evidence/${CASE}__baseline_submission__"*.json 2>/dev/null | head -n1 || true)"
[[ -n "$LATEST" ]] && cp "$LATEST" "$OUT/baseline.evaluation.json"

echo "Baseline-only run complete."
echo "Case: $CASE"
echo "Run id: $RUN_ID"
echo "Agent exit: $AGENT_RC"
echo "Evaluator exit: $EVAL_RC"
echo "Evidence: $OUT"
