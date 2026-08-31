#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 CASE_ID" >&2
  echo "Example: $0 payment_unit_drift" >&2
  exit 2
fi

CASE="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
STATE_FILE="$ROOT/evidence/active/$CASE.json"
TRACE_PY="$ROOT/benchmark/opencode_trace.py"
OPENCODE_BIN="${DRIFTGUARD_OPENCODE_BIN:-opencode}"
MODEL="${DRIFTGUARD_OPENCODE_MODEL:-}"
VARIANT="${DRIFTGUARD_OPENCODE_VARIANT:-max}"
REPAIR_AGENT="${DRIFTGUARD_OPENCODE_AGENT:-build}"
VERIFIER_AGENT="${DRIFTGUARD_OPENCODE_VERIFIER_AGENT:-build}"
RETRY_ON_ABSTAIN="${DRIFTGUARD_RETRY_ON_ABSTAIN:-0}"
AUTO_APPROVE="${DRIFTGUARD_OPENCODE_AUTO:-0}"
BASELINE_SYSTEM="${DRIFTGUARD_BASELINE_SYSTEM:-baseline_v4}"
FINAL_SYSTEM="${DRIFTGUARD_FINAL_SYSTEM:-driftguard_v1}"
USAGE_MULTIPLIER="${DRIFTGUARD_OPENCODE_USAGE_MULTIPLIER:-2}"
WEB_ENABLED="${DRIFTGUARD_OPENCODE_WEB:-1}"
WEB_AUTOSTART="${DRIFTGUARD_OPENCODE_WEB_AUTOSTART:-1}"
WEB_HELPER="$ROOT/scripts/opencode_web.sh"
WEB_URL="${DRIFTGUARD_OPENCODE_WEB_URL:-}"
WEB_OPEN_SESSION="${DRIFTGUARD_OPENCODE_WEB_OPEN_SESSION:-1}"

command -v "$OPENCODE_BIN" >/dev/null 2>&1 || {
  echo "OpenCode CLI not found: $OPENCODE_BIN" >&2
  exit 2
}
command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 2; }
[[ -x "$VENV/bin/python" ]] || { echo "Run ./scripts/bootstrap.sh first" >&2; exit 2; }
[[ -f "$ROOT/evidence/golden_snapshot.json" ]] || { echo "Run ./scripts/capture_golden.sh first" >&2; exit 2; }
[[ -f "$ROOT/benchmark/cases/$CASE.json" ]] || { echo "Unknown case: $CASE" >&2; exit 2; }

UV_RUN=(uv run --no-project --python "$VENV/bin/python")

strip_ansi() {
  sed -r 's/\x1B\[[0-9;]*[mK]//g'
}

open_url_best_effort() {
  local url="$1"
  [[ "$WEB_OPEN_SESSION" == "1" ]] || return 0
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  elif command -v wslview >/dev/null 2>&1; then
    wslview "$url" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
  fi
}

resolve_model() {
  if [[ -n "$MODEL" ]]; then
    return 0
  fi
  mapfile -t matches < <(
    NO_COLOR=1 "$OPENCODE_BIN" models 2>/dev/null \
      | strip_ansi \
      | awk '{$1=$1; print}' \
      | grep -Ei '(^|/)glm-5\.3-flash([[:space:]]|$)' \
      | awk '{print $1}' \
      | sort -u || true
  )
  if [[ ${#matches[@]} -eq 1 ]]; then
    MODEL="${matches[0]}"
    return 0
  fi
  echo "Could not uniquely resolve GLM-5.3-Flash from 'opencode models'." >&2
  if [[ ${#matches[@]} -gt 0 ]]; then
    echo "Candidates:" >&2
    printf '  %s\n' "${matches[@]}" >&2
  fi
  echo "Set DRIFTGUARD_OPENCODE_MODEL to the exact provider/model shown by 'opencode models'." >&2
  exit 2
}

resolve_model

# 1) Prepare a fresh blinded incident workspace.
PREP_LOG="$(mktemp)"
"$ROOT/scripts/prepare_case.sh" "$CASE" | tee "$PREP_LOG"
[[ -f "$STATE_FILE" ]] || { echo "Missing active case state: $STATE_FILE" >&2; exit 2; }

readarray -t STATE < <("${UV_RUN[@]}" python - "$STATE_FILE" <<'PY'
import json, sys
x=json.load(open(sys.argv[1]))
print(x["run_id"])
print(x["workspace"])
print(x["base"])
PY
)
RUN_ID="${STATE[0]}"
WORK="${STATE[1]}"
BASE="${STATE[2]}"
RUN_DIR="$ROOT/evidence/runs/$CASE/$RUN_ID"
mkdir -p "$RUN_DIR"
mv "$PREP_LOG" "$RUN_DIR/prepare.log"

# Route automated sessions through OpenCode's web server so baseline, verifier,
# and retry operations are visible live in the browser. OpenCode documents
# `opencode web` for the browser UI and `opencode run --attach URL` for scripted
# clients that share that server/session state.
if [[ "$WEB_ENABLED" == "1" ]]; then
  if [[ -n "$WEB_URL" ]]; then
    if ! DRIFTGUARD_OPENCODE_WEB_URL="$WEB_URL" "$WEB_HELPER" status >/dev/null; then
      echo "Configured OpenCode web server is unavailable: $WEB_URL" >&2
      exit 2
    fi
  elif [[ "$WEB_AUTOSTART" == "1" ]]; then
    WEB_URL="$(DRIFTGUARD_OPENCODE_WEB_CWD="$WORK" "$WEB_HELPER" ensure)"
  else
    echo "DRIFTGUARD_OPENCODE_WEB=1 but no server URL is configured and autostart is disabled." >&2
    echo "Run ./scripts/opencode_web.sh start or set DRIFTGUARD_OPENCODE_WEB_URL." >&2
    exit 2
  fi
  echo "OpenCode Web: $WEB_URL"
  echo "Agent stages attach to this server. DriftGuard will print a direct web URL for each session."
fi

OPENCODE_COMMON=(run --model "$MODEL" --variant "$VARIANT" --format json --thinking)
if [[ "$WEB_ENABLED" == "1" ]]; then
  OPENCODE_COMMON+=(--attach "$WEB_URL")
fi
if [[ "$AUTO_APPROVE" == "1" ]]; then
  OPENCODE_COMMON+=(--auto)
fi

latest_eval() {
  local system="$1"
  ls -1t "$ROOT/evidence/${CASE}__${system}__"*.json 2>/dev/null | head -n 1 || true
}

run_eval() {
  local system="$1" out_file="$2"
  local rc=0
  if "$ROOT/scripts/evaluate_case.sh" "$CASE" "$system"; then
    rc=0
  else
    rc=$?
  fi
  local src
  src="$(latest_eval "$system")"
  if [[ -n "$src" && -f "$src" ]]; then
    cp "$src" "$out_file"
  else
    echo "Evaluator did not produce a result for $system" >&2
    return 2
  fi
  return "$rc"
}

run_opencode_stage() {
  local stage="$1" agent="$2" prompt="$3" run_dir="$4" work="$5"
  local events="$run_dir/${stage}.events.jsonl"
  local stderr_file="$run_dir/${stage}.stderr.log"
  local export_file="$run_dir/${stage}.export.json"
  local export_stderr="$run_dir/${stage}.export.stderr.log"
  local summary="$run_dir/${stage}.summary.json"
  local final_text="$run_dir/${stage}.final.txt"
  local title="DriftGuard ${stage} ${RUN_ID}"

  echo
  echo "=== OpenCode stage: $stage ==="
  echo "agent=$agent model=$MODEL variant=$VARIANT"

  : > "$events"
  local web_watch_pid=""
  if [[ "$WEB_ENABLED" == "1" ]]; then
    local project_url
    project_url="$("${UV_RUN[@]}" python "$TRACE_PY" web-url "$WEB_URL" "$work")"
    printf '%s\n' "$project_url" > "$run_dir/${stage}.project_web_url.txt"
    echo "OpenCode project view: $project_url"

    # OpenCode Web currently has versions where CLI-created sessions exist on
    # the backend but Home does not register/render their project. Watch the raw
    # event stream for the session id and deep-link directly to that session as
    # soon as it appears so the browser can follow the live run.
    (
      for _ in {1..1800}; do
        local_sid="$("${UV_RUN[@]}" python "$TRACE_PY" session-id "$events" 2>/dev/null || true)"
        if [[ -n "$local_sid" ]]; then
          local_url="$("${UV_RUN[@]}" python "$TRACE_PY" web-url "$WEB_URL" "$work" --session-id "$local_sid")"
          printf '%s\n' "$local_url" > "$run_dir/${stage}.web_url.txt"
          echo "OpenCode live session ($stage): $local_url" >&2
          open_url_best_effort "$local_url"
          exit 0
        fi
        sleep 0.1
      done
    ) &
    web_watch_pid=$!
  fi

  local rc=0
  if (
    cd "$work"
    # Expose the benchmark's pinned Python/dbt toolchain on PATH for every
    # agent stage. This avoids agent-specific environment bootstrapping while
    # keeping the workspace itself blinded.
    PATH="$VENV/bin:$PATH" \
    VIRTUAL_ENV="$VENV" \
    NO_COLOR=1 \
      "$OPENCODE_BIN" "${OPENCODE_COMMON[@]}" \
        --agent "$agent" \
        --dir "$work" \
        --title "$title" \
        "$prompt"
  ) > >(tee "$events") 2> >(tee "$stderr_file" >&2); then
    rc=0
  else
    rc=$?
  fi

  if [[ -n "$web_watch_pid" ]]; then
    # Give the watcher a brief chance to observe the final buffered event, then
    # stop it so a malformed/no-session run never delays orchestration.
    for _ in {1..20}; do
      kill -0 "$web_watch_pid" 2>/dev/null || break
      sleep 0.05
    done
    if kill -0 "$web_watch_pid" 2>/dev/null; then
      kill "$web_watch_pid" 2>/dev/null || true
    fi
    wait "$web_watch_pid" 2>/dev/null || true
  fi

  local sid=""
  sid="$("${UV_RUN[@]}" python "$TRACE_PY" session-id "$events" 2>/dev/null || true)"
  if [[ -n "$sid" && "$WEB_ENABLED" == "1" ]]; then
    local session_web_url
    session_web_url="$("${UV_RUN[@]}" python "$TRACE_PY" web-url "$WEB_URL" "$work" --session-id "$sid")"
    if [[ ! -f "$run_dir/${stage}.web_url.txt" ]]; then
      printf '%s\n' "$session_web_url" > "$run_dir/${stage}.web_url.txt"
      echo "OpenCode session ($stage): $session_web_url"
      open_url_best_effort "$session_web_url"
    fi
  fi
  if [[ -n "$sid" ]]; then
    local export_rc=0
    if NO_COLOR=1 "$OPENCODE_BIN" export "$sid" >"$export_file" 2>"$export_stderr"; then
      export_rc=0
    else
      export_rc=$?
    fi
    if [[ $export_rc -ne 0 ]]; then
      echo "Warning: OpenCode session export failed for $sid (rc=$export_rc). Raw events are still preserved." >&2
      rm -f "$export_file"
    fi
  else
    echo "Warning: no OpenCode session id found in $events; raw event stream is preserved." >&2
  fi

  local summarize_args=(python "$TRACE_PY" summarize "$events" --output "$summary" --text-output "$final_text")
  if [[ -f "$export_file" ]]; then
    summarize_args+=(--export "$export_file")
  fi
  "${UV_RUN[@]}" "${summarize_args[@]}" >/dev/null

  printf '%s\n' "$rc" > "$run_dir/${stage}.exit_code"
  echo "Trajectory: $events"
  [[ -f "$export_file" ]] && echo "Session export: $export_file"
  [[ -f "$run_dir/${stage}.web_url.txt" ]] && echo "Web session: $(cat "$run_dir/${stage}.web_url.txt")"
  echo "Final response: $final_text"
  return "$rc"
}

# Harness-only files are visible to agents when needed but excluded from Git
# repair metrics. Prompts are passed directly on the CLI, so no outside-
# workspace file permission is required.
mkdir -p "$WORK/.driftguard"
printf '%s\n' '.driftguard/' >> "$WORK/.git/info/exclude"

"${UV_RUN[@]}" python - "$RUN_DIR/manifest.start.json" <<PY
import json, pathlib, subprocess
out=pathlib.Path(r"$RUN_DIR/manifest.start.json")
payload={
  "case": r"$CASE",
  "run_id": r"$RUN_ID",
  "workspace": r"$WORK",
  "incident_base": r"$BASE",
  "opencode_bin": r"$OPENCODE_BIN",
  "opencode_version": subprocess.run([r"$OPENCODE_BIN", "--version"], text=True, capture_output=True).stdout.strip(),
  "model": r"$MODEL",
  "variant": r"$VARIANT",
  "usage_multiplier": float(r"$USAGE_MULTIPLIER"),
  "repair_agent": r"$REPAIR_AGENT",
  "verifier_agent": r"$VERIFIER_AGENT",
  "opencode_web_enabled": bool(int(r"$WEB_ENABLED")),
  "opencode_web_url": r"$WEB_URL" if bool(int(r"$WEB_ENABLED")) else None,
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True)+"\n")
PY

# 2) Baseline repair in a fresh OpenCode session.
BASELINE_PROMPT="$(cat "$ROOT/prompts/baseline.md")"
if run_opencode_stage "baseline" "$REPAIR_AGENT" "$BASELINE_PROMPT" "$RUN_DIR" "$WORK"; then
  BASELINE_AGENT_RC=0
else
  BASELINE_AGENT_RC=$?
fi

if run_eval "$BASELINE_SYSTEM" "$RUN_DIR/baseline.evaluation.json"; then
  BASELINE_EVAL_RC=0
else
  BASELINE_EVAL_RC=$?
fi

# 3) Generate machine evidence and make a verifier-visible copy in workspace.
"$ROOT/scripts/generate_verifier_evidence.sh" "$CASE" | tee "$RUN_DIR/verifier_evidence_generation.log"
cp "$WORK/.driftguard/verifier_evidence.json" "$RUN_DIR/verifier_evidence.json"

# 4) Independent verifier in a fresh OpenCode session. Snapshot the candidate
# patch first so any verifier edit becomes an explicit protocol violation.
git -C "$WORK" diff --binary "$BASE" > "$RUN_DIR/candidate_before_verifier.patch"
git -C "$WORK" status --porcelain=v1 > "$RUN_DIR/status_before_verifier.txt"

VERIFIER_PROMPT="$(cat "$ROOT/prompts/verifier_agent.md")

The machine-generated report is already inside this workspace at:
  .driftguard/verifier_evidence.json
Do not request files outside this workspace. Do not edit repository files."

if run_opencode_stage "verifier" "$VERIFIER_AGENT" "$VERIFIER_PROMPT" "$RUN_DIR" "$WORK"; then
  VERIFIER_AGENT_RC=0
else
  VERIFIER_AGENT_RC=$?
fi

git -C "$WORK" diff --binary "$BASE" > "$RUN_DIR/candidate_after_verifier.patch"
git -C "$WORK" status --porcelain=v1 > "$RUN_DIR/status_after_verifier.txt"
if ! cmp -s "$RUN_DIR/candidate_before_verifier.patch" "$RUN_DIR/candidate_after_verifier.patch" || ! cmp -s "$RUN_DIR/status_before_verifier.txt" "$RUN_DIR/status_after_verifier.txt"; then
  echo "ERROR: verifier modified the candidate repair. This violates the verifier protocol." >&2
  cp "$RUN_DIR/candidate_after_verifier.patch" "$RUN_DIR/verifier_protocol_violation.patch"
  exit 3
fi

VERDICT="$("${UV_RUN[@]}" python "$TRACE_PY" verdict "$RUN_DIR/verifier.final.txt" 2>/dev/null || true)"
if [[ -z "$VERDICT" ]]; then
  echo "Could not safely parse verifier verdict." >&2
  echo "Accepted forms include '# FAIL', '**PASS**', 'Verdict: ABSTAIN', JSON verdicts," >&2
  echo "or the preferred 'DRIFTGUARD_VERDICT: PASS|FAIL|ABSTAIN' marker." >&2
  echo "Conflicting verdict markers intentionally fail closed." >&2
  echo "See $RUN_DIR/verifier.final.txt" >&2
  exit 4
fi
printf '%s\n' "$VERDICT" | tee "$RUN_DIR/verifier.verdict"

# 5) Retry only when the verifier found a concrete failure. ABSTAIN is kept as
# a human-review outcome by default; set DRIFTGUARD_RETRY_ON_ABSTAIN=1 to retry.
RETRY_RAN=0
if [[ "$VERDICT" == "FAIL" || ( "$VERDICT" == "ABSTAIN" && "$RETRY_ON_ABSTAIN" == "1" ) ]]; then
  RETRY_RAN=1
  cp "$RUN_DIR/verifier.final.txt" "$WORK/.driftguard/verifier_feedback.md"
  RETRY_PROMPT="$(cat "$ROOT/prompts/repair_retry.md")

The verifier's exact feedback is available inside this workspace at:
  .driftguard/verifier_feedback.md
Read it, independently validate it against the repository, then make the smallest safe correction."
  if run_opencode_stage "retry" "$REPAIR_AGENT" "$RETRY_PROMPT" "$RUN_DIR" "$WORK"; then
    RETRY_AGENT_RC=0
  else
    RETRY_AGENT_RC=$?
  fi
else
  RETRY_AGENT_RC=0
  echo "No retry launched for verifier verdict: $VERDICT"
fi

# 6) Final hidden evaluation on whatever state the workflow leaves behind.
if run_eval "$FINAL_SYSTEM" "$RUN_DIR/final.evaluation.json"; then
  FINAL_EVAL_RC=0
else
  FINAL_EVAL_RC=$?
fi

# Preserve final patch and a compact machine-readable experiment summary.
git -C "$WORK" diff --binary "$BASE" > "$RUN_DIR/final.patch"
"${UV_RUN[@]}" python - "$RUN_DIR/flow_summary.json" \
  "$RUN_DIR/manifest.start.json" "$RUN_DIR/baseline.evaluation.json" \
  "$RUN_DIR/final.evaluation.json" "$RUN_DIR/verifier.summary.json" <<PY
import json, pathlib, sys
out, manifest_p, baseline_p, final_p, verifier_p = map(pathlib.Path, sys.argv[1:])
manifest=json.loads(manifest_p.read_text())
baseline=json.loads(baseline_p.read_text())
final=json.loads(final_p.read_text())
verifier=json.loads(verifier_p.read_text())
payload={
  **manifest,
  "baseline_agent_exit_code": int(r"$BASELINE_AGENT_RC"),
  "baseline_evaluator_exit_code": int(r"$BASELINE_EVAL_RC"),
  "baseline_verified_recovery": baseline.get("verified_recovery"),
  "baseline_value_pass": baseline.get("value_pass"),
  "baseline_schema_pass": baseline.get("schema_pass"),
  "verifier_agent_exit_code": int(r"$VERIFIER_AGENT_RC"),
  "verifier_verdict": r"$VERDICT",
  "retry_ran": bool(int(r"$RETRY_RAN")),
  "retry_agent_exit_code": int(r"$RETRY_AGENT_RC"),
  "final_evaluator_exit_code": int(r"$FINAL_EVAL_RC"),
  "final_verified_recovery": final.get("verified_recovery"),
  "final_value_pass": final.get("value_pass"),
  "final_schema_pass": final.get("schema_pass"),
  "web_sessions": {
    stage: (out.parent / f"{stage}.web_url.txt").read_text().strip()
    for stage in ("baseline", "verifier", "retry")
    if (out.parent / f"{stage}.web_url.txt").exists()
  },
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True)+"\n")
print(json.dumps(payload, indent=2, sort_keys=True))
PY

cat <<MSG

=== DriftGuard OpenCode flow complete ===
Case:               $CASE
Run id:             $RUN_ID
Model:              $MODEL
Variant:            $VARIANT
Usage multiplier:   ${USAGE_MULTIPLIER}x (recorded metadata)
Baseline recovered: $("${UV_RUN[@]}" python -c 'import json,sys; print(json.load(open(sys.argv[1]))["verified_recovery"])' "$RUN_DIR/baseline.evaluation.json")
Verifier verdict:   $VERDICT
Retry ran:          $RETRY_RAN
Final recovered:    $("${UV_RUN[@]}" python -c 'import json,sys; print(json.load(open(sys.argv[1]))["verified_recovery"])' "$RUN_DIR/final.evaluation.json")
Evidence bundle:    $RUN_DIR
Summary:            $RUN_DIR/flow_summary.json
OpenCode Web:        ${WEB_URL:-disabled}
Web session links:   $RUN_DIR/*.web_url.txt
MSG

# The flow itself completed even when the final benchmark result is a failure;
# callers can inspect flow_summary.json to distinguish experimental outcomes.
exit 0
