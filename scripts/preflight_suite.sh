#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
OUT_DIR="$ROOT/evidence/preflight"
UV_RUN=(uv run --no-project --python "$VENV/bin/python")

command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 2; }
[[ -x "$VENV/bin/python" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }
[[ -f "$ROOT/evidence/golden_snapshot.json" ]] || { echo "Run ./scripts/capture_golden.sh first" >&2; exit 2; }
mkdir -p "$OUT_DIR"

if [[ $# -gt 0 ]]; then
  CASES=("$@")
else
  CASE_INDEX="$ROOT/benchmark/cases/index.txt"
  if [[ -f "$CASE_INDEX" ]]; then
    mapfile -t CASES < <(grep -Ev '^[[:space:]]*(#|$)' "$CASE_INDEX")
  else
    mapfile -t CASES < <(find "$ROOT/benchmark/cases" -maxdepth 1 -type f -name '*.json' -printf '%f\n' | sed 's/\.json$//' | sort)
  fi
fi

FAILED=0
printf '%-42s %-18s %-12s %-12s %-8s\n' CASE FAMILY BUILD CONTRACT STATUS
printf '%-42s %-18s %-12s %-12s %-8s\n' "------------------------------------------" "------------------" "------------" "------------" "--------"

for CASE in "${CASES[@]}"; do
  CASE_FILE="$ROOT/benchmark/cases/$CASE.json"
  [[ -f "$CASE_FILE" ]] || { echo "Unknown case: $CASE" >&2; FAILED=1; continue; }

  "$ROOT/scripts/prepare_case.sh" "$CASE" >/dev/null
  STATE_FILE="$ROOT/evidence/active/$CASE.json"
  readarray -t STATE < <("${UV_RUN[@]}" python - "$STATE_FILE" <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); print(x['workspace']); print(x['base'])
PY
)
  WORK="${STATE[0]}"; BASE="${STATE[1]}"
  OUT="$OUT_DIR/$CASE.json"

  set +e
  PATH="$VENV/bin:$PATH" VIRTUAL_ENV="$VENV" \
    "${UV_RUN[@]}" python "$ROOT/benchmark/evaluate.py" \
      "$CASE" "$WORK" --system preflight_control --base "$BASE" --output "$OUT" >/dev/null
  set -e

  readarray -t CHECK < <("${UV_RUN[@]}" python - "$CASE_FILE" "$OUT" <<'PY'
import json,sys
case=json.load(open(sys.argv[1])); result=json.load(open(sys.argv[2])); exp=case.get('expected_pre_repair',{})
family=case.get('family','unknown')
build=result.get('build_pass'); contract=result.get('contract_pass')
ok=(build is exp.get('build_pass')) and (contract is exp.get('contract_pass')) and not result.get('changed_paths')
print(family); print(str(build)); print(str(contract)); print('PASS' if ok else 'FAIL')
PY
)
  printf '%-42s %-18s %-12s %-12s %-8s\n' "$CASE" "${CHECK[0]}" "${CHECK[1]}" "${CHECK[2]}" "${CHECK[3]}"
  [[ "${CHECK[3]}" == "PASS" ]] || FAILED=1

  # Preflight workspaces are controls, not agent trajectories. Remove them so
  # later benchmark runs are clean and only the JSON result remains.
  rm -rf "$WORK"
  rm -f "$STATE_FILE"
done

if [[ $FAILED -ne 0 ]]; then
  echo >&2
  echo "Preflight found one or more incidents whose actual control behavior does not match the case design." >&2
  echo "Do not spend agent runs yet. Inspect evidence/preflight/*.json and revise those incidents." >&2
  exit 1
fi

echo
echo "All ${#CASES[@]} incident controls match their declared pre-repair behavior."
echo "Preflight evidence: $OUT_DIR"
