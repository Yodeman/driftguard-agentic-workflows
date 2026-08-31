#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="$ROOT/scripts/run_opencode_flow.sh"
WEB_HELPER="$ROOT/scripts/opencode_web.sh"
WEB_ENABLED="${DRIFTGUARD_OPENCODE_WEB:-1}"

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

# If the caller supplied a server, validate it. Otherwise let the first flow
# start OpenCode Web from its freshly prepared blinded workspace. That gives
# the browser's initial project context the best chance of matching the first
# visible run. Later cases reuse the same backend and expose direct per-session
# deep links, which do not depend on Web Home's client-side project registry.
WEB_URL="${DRIFTGUARD_OPENCODE_WEB_URL:-}"
if [[ "$WEB_ENABLED" == "1" && -n "$WEB_URL" ]]; then
  DRIFTGUARD_OPENCODE_WEB_URL="$WEB_URL" "$WEB_HELPER" status >/dev/null || {
    echo "Configured OpenCode web server is unavailable: $WEB_URL" >&2
    exit 2
  }
  echo "OpenCode Web: $WEB_URL"
fi

FAILED=0
for case_id in "${CASES[@]}"; do
  echo
  echo "################################################################"
  echo "# DriftGuard OpenCode flow: $case_id"
  echo "################################################################"

  rc=0
  if [[ "$WEB_ENABLED" == "1" && -n "$WEB_URL" ]]; then
    DRIFTGUARD_OPENCODE_WEB_URL="$WEB_URL" "$FLOW" "$case_id" || rc=$?
  else
    "$FLOW" "$case_id" || rc=$?
  fi

  if [[ $rc -ne 0 ]]; then
    echo "Flow infrastructure failed for case: $case_id" >&2
    FAILED=1
  fi

  if [[ "$WEB_ENABLED" == "1" && -z "$WEB_URL" ]]; then
    WEB_URL="$($WEB_HELPER url)"
    if "$WEB_HELPER" status >/dev/null 2>&1; then
      echo "Reusing OpenCode Web for remaining suite cases: $WEB_URL"
    else
      echo "Warning: first flow did not leave a healthy managed OpenCode Web server." >&2
      WEB_URL=""
    fi
  fi
done

if [[ $FAILED -ne 0 ]]; then
  echo "One or more flows failed at the orchestration/infrastructure level." >&2
  exit 1
fi

echo
printf 'Completed %d case flow(s). See evidence/runs/<case>/<run_id>/flow_summary.json\n' "${#CASES[@]}"

echo
echo "Generating aggregate benchmark report from latest completed runs..."
"$ROOT/scripts/summarize_suite.sh" || echo "Warning: aggregate report generation failed; per-run evidence is still preserved." >&2
if [[ "$WEB_ENABLED" == "1" && -n "$WEB_URL" ]]; then
  echo "OpenCode Web remains running for review: $WEB_URL"
  echo "Each evidence bundle contains baseline/verifier/retry .web_url.txt deep links."
  echo "Stop the DriftGuard-managed server with: ./scripts/opencode_web.sh stop"
fi
