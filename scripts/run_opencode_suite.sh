#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="$ROOT/scripts/run_opencode_flow.sh"
WEB_HELPER="$ROOT/scripts/opencode_web.sh"
WEB_ENABLED="${DRIFTGUARD_OPENCODE_WEB:-1}"
QUIET="${DRIFTGUARD_SUITE_QUIET:-0}"
# A stable, case-neutral path keeps all suite sessions in one OpenCode project,
# so the browser can stay on one project tab. The directory is fully replaced
# before every case by prepare_case.sh, preserving case isolation.
SUITE_WORKSPACE="${DRIFTGUARD_SUITE_WORKSPACE:-$ROOT/workspaces/opencode_suite}"

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

[[ ${#CASES[@]} -gt 0 ]] || { echo "No benchmark cases found." >&2; exit 2; }

SUITE_ID="suite_$(date -u +%Y%m%dT%H%M%SZ)"
SUITE_DIR="$ROOT/evidence/suites/$SUITE_ID"
mkdir -p "$SUITE_DIR"
printf '%s\n' "${CASES[@]}" > "$SUITE_DIR/cases.txt"
printf '%s\n' "$SUITE_WORKSPACE" > "$SUITE_DIR/workspace.txt"

WEB_URL="${DRIFTGUARD_OPENCODE_WEB_URL:-}"
if [[ "$WEB_ENABLED" == "1" && -n "$WEB_URL" ]]; then
  DRIFTGUARD_OPENCODE_WEB_URL="$WEB_URL" "$WEB_HELPER" status >/dev/null || {
    echo "Configured OpenCode web server is unavailable: $WEB_URL" >&2
    exit 2
  }
  echo "OpenCode Web: $WEB_URL"
fi

FAILED=0
FAILED_CASES=()
for case_id in "${CASES[@]}"; do
  echo
  echo "################################################################"
  echo "# DriftGuard OpenCode flow: $case_id"
  echo "################################################################"
  log="$SUITE_DIR/${case_id}.log"

  rc=0
  if [[ "$WEB_ENABLED" == "1" && -n "$WEB_URL" ]]; then
    if [[ "$QUIET" == "1" ]]; then
      DRIFTGUARD_WORKSPACE_DIR="$SUITE_WORKSPACE" \
      DRIFTGUARD_OPENCODE_WEB_URL="$WEB_URL" \
      DRIFTGUARD_OPENCODE_WEB_OPEN_SESSION=0 \
        "$FLOW" "$case_id" >"$log" 2>&1 || rc=$?
    else
      DRIFTGUARD_WORKSPACE_DIR="$SUITE_WORKSPACE" \
      DRIFTGUARD_OPENCODE_WEB_URL="$WEB_URL" \
      DRIFTGUARD_OPENCODE_WEB_OPEN_SESSION=0 \
        "$FLOW" "$case_id" > >(tee "$log") 2>&1 || rc=$?
    fi
  else
    if [[ "$QUIET" == "1" ]]; then
      DRIFTGUARD_WORKSPACE_DIR="$SUITE_WORKSPACE" \
      DRIFTGUARD_OPENCODE_WEB_OPEN_SESSION=0 \
        "$FLOW" "$case_id" >"$log" 2>&1 || rc=$?
    else
      DRIFTGUARD_WORKSPACE_DIR="$SUITE_WORKSPACE" \
      DRIFTGUARD_OPENCODE_WEB_OPEN_SESSION=0 \
        "$FLOW" "$case_id" > >(tee "$log") 2>&1 || rc=$?
    fi
  fi

  printf '%s\n' "$rc" > "$SUITE_DIR/${case_id}.exit_code"
  if [[ $rc -ne 0 ]]; then
    echo "Flow infrastructure failed for case: $case_id (rc=$rc; log=$log)" >&2
    FAILED=1
    FAILED_CASES+=("$case_id")
  fi

  if [[ "$WEB_ENABLED" == "1" && -z "$WEB_URL" ]]; then
    WEB_URL="$($WEB_HELPER url)"
    if "$WEB_HELPER" status >/dev/null 2>&1; then
      echo "Reusing OpenCode Web for remaining suite cases: $WEB_URL"
    else
      echo "Warning: flow did not leave a healthy managed OpenCode Web server." >&2
      WEB_URL=""
    fi
  fi
done

# Always aggregate what completed, even if one or more flows failed. The report
# explicitly lists missing cases, so partial evidence can never be mistaken for
# a complete benchmark.
echo
echo "Generating aggregate benchmark report from completed runs..."
SUMMARY_RC=0
"$ROOT/scripts/summarize_suite.sh" --expected-cases "${CASES[@]}" || SUMMARY_RC=$?
printf '%s\n' "$SUMMARY_RC" > "$SUITE_DIR/summary.exit_code"

python_status="$ROOT/evidence/summary/suite_status.json"
if [[ -f "$python_status" ]]; then
  cp "$python_status" "$SUITE_DIR/suite_status.json"
fi

if [[ ${#FAILED_CASES[@]} -gt 0 ]]; then
  printf '%s\n' "${FAILED_CASES[@]}" > "$SUITE_DIR/failed_cases.txt"
fi

printf '\nCompleted %d requested case flow(s). Suite evidence: %s\n' "${#CASES[@]}" "$SUITE_DIR"
echo "Aggregate report: $ROOT/evidence/summary/report.md"

if [[ "$WEB_ENABLED" == "1" && -n "$WEB_URL" ]]; then
  echo "OpenCode Web remains running for review: $WEB_URL"
  echo "Suite runs use one stable project directory, so one project tab can show all sessions."
  echo "Direct session URLs remain archived under each run but are not auto-opened."
  echo "Stop the managed server with: ./scripts/opencode_web.sh stop"
fi

if [[ $FAILED -ne 0 ]]; then
  echo "One or more flows failed at the orchestration/infrastructure level; the aggregate report is partial." >&2
  exit 1
fi
if [[ $SUMMARY_RC -ne 0 ]]; then
  echo "Aggregate report generation failed." >&2
  exit "$SUMMARY_RC"
fi
exit 0
