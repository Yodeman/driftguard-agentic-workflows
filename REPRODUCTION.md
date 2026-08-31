# Reproduction Guide

This guide is written for a reviewer starting from a clean environment.

## 1. What is reproduced

The repository contains:

- the **general-purpose coding-agent baseline**;
- the **DriftGuard Iteration-2 workflow**;
- a frozen **12-case deterministic benchmark**;
- preflight validation;
- a hidden golden-contract evaluator;
- OpenCode trajectory capture and aggregate reporting.

The benchmark uses the public synthetic dbt Jaffle Shop DuckDB project. No private data or credentials are required.

## 2. Tested toolchain

The recorded benchmark environment used:

| Component | Recorded version/configuration |
|---|---|
| `uv` | 0.11.8 |
| Python | 3.13.13 |
| dbt-core | 1.11.6 |
| dbt-duckdb | 1.10.1 |
| Jaffle Shop DuckDB | commit `36bde6cba69d962b83be1d52fc65a0dce1cb4ebb` |
| OpenCode | 1.18.25 in the frozen agent runs |
| Agent model | `opencode-go/glm-5.3-flash` |
| OpenCode variant | `max` |
| OpenCode agent | `build` |
| Recorded Go usage multiplier | 2x metadata |

The bootstrap script pins the Jaffle Shop commit for the submission package. OpenCode/model availability is external to this repository, so reviewers should configure a compatible OpenCode provider before running agent experiments.

## 3. System prerequisites

Install:

```text
git
bash
curl
uv
opencode
```

Confirm:

```bash
git --version
uv --version
opencode --version
opencode models
```

The recorded model should appear as `opencode-go/glm-5.3-flash`. If your provider name differs, set the exact model string:

```bash
export DRIFTGUARD_OPENCODE_MODEL='provider/glm-5.3-flash'
```

## 4. Bootstrap from a clean clone

From the repository root:

```bash
./scripts/bootstrap.sh
```

Expected effects:

1. clone/fetch the pinned Jaffle Shop DuckDB project under `vendor/jaffle_shop_duckdb`;
2. create `.venv` with Python 3.13 via `uv`;
3. install the pinned project's requirements;
4. record the actual environment under `evidence/environment.txt`.

The recorded experiment printed versions equivalent to:

```text
uv: uv 0.11.8
Python actual: Python 3.13.13
dbt-core: 1.11.6
dbt-duckdb: 1.10.1
Jaffle Shop commit: 36bde6cba69d962b83be1d52fc65a0dce1cb4ebb
```

## 5. Capture the known-good contract

```bash
./scripts/capture_golden.sh
```

Expected result on the frozen project:

```text
PASS=28 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=28
Golden semantic snapshot captured.
```

The snapshot covers the logical staging/mart outputs used by the evaluator.

## 6. Validate the benchmark before using model calls

```bash
./scripts/preflight_suite.sh
```

Expected final line:

```text
All 12 incident controls match their declared pre-repair behavior.
```

Expected control profile:

- 3 structural cases: `build_pass=false`, `contract_pass=false`;
- 9 non-structural cases: `build_pass=true`, `contract_pass=false`.

If preflight fails, do not run the agent suite; the benchmark and environment are not matching the frozen design.

## 7. Reproduce the baseline

### Option A — one baseline case only

Use the helper added for submission reproducibility:

```bash
./scripts/run_baseline_only.sh payment_unit_drift
```

The helper:

1. creates a fresh blinded incident workspace;
2. starts a fresh OpenCode `build` session with `prompts/baseline.md`;
3. does not expose the golden evaluator to the agent;
4. evaluates the resulting patch;
5. stores the trajectory and JSON result under `evidence/baseline_only/...`.

Try other frozen cases by replacing the case id with one from `benchmark/cases/index.txt`.

### Option B — baseline embedded in the complete flow

Every full DriftGuard flow first runs the exact baseline and writes `baseline.evaluation.json` before verification begins:

```bash
./scripts/run_opencode_flow.sh payment_unit_drift
```

This is how the frozen 12-case comparison was collected; baseline and final solution therefore see the same incident instance within each flow.

## 8. Reproduce the final DriftGuard solution

One case:

```bash
./scripts/run_opencode_flow.sh payment_unit_drift
```

All frozen cases:

```bash
./scripts/run_opencode_suite.sh
```

The final workflow is:

```text
baseline repair
  -> hidden baseline evaluation
  -> deterministic contract gate
  -> semantic verifier only if unresolved
  -> compatibility retry when verifier FAILs
  -> immutable-source guard / bounded correction
  -> hidden final evaluation
```

OpenCode Web is enabled by default at `http://127.0.0.1:4096` for trajectory review. Suite runs use one stable project path so one browser project tab can show the sessions. Disable Web mode if desired:

```bash
export DRIFTGUARD_OPENCODE_WEB=0
```

## 9. Generate the evaluation report

After runs:

```bash
./scripts/summarize_suite.sh
```

Expected output files:

```text
evidence/summary/report.md
evidence/summary/aggregate.json
evidence/summary/latest_runs.csv
evidence/summary/latest_runs.json
evidence/summary/suite_status.json
```

The official frozen Iteration-2 aggregate was:

```json
{
  "cases": 12,
  "complete": true,
  "baseline_verified": 6,
  "baseline_vrr_percent": 50.0,
  "final_verified": 11,
  "final_vrr_percent": 91.7,
  "absolute_vrr_change_pp": 41.7,
  "baseline_failures_rescued": 5,
  "regressions": 0,
  "deterministic_gate_passes": 6,
  "semantic_verifier_calls": 6,
  "verifier_fail_precision_percent": 100.0,
  "verifier_fail_recall_percent": 100.0
}
```

## 10. Exact evaluation command for an already-prepared workspace

The normal helper is:

```bash
./scripts/evaluate_case.sh CASE_ID SYSTEM_LABEL
```

Example:

```bash
./scripts/evaluate_case.sh payment_unit_drift manual_check
```

The evaluator rebuilds the project and checks the candidate against the hidden known-good logical contract plus protected-file policies.

## 11. Evidence and trajectories

Each complete agentic run stores:

```text
evidence/runs/<case>/<run_id>/
├── baseline.events.jsonl
├── baseline.export.json               # when OpenCode export succeeds
├── baseline.final.txt
├── baseline.evaluation.json
├── verifier_evidence.json
├── verifier.events.jsonl              # semantic-verifier cases
├── verifier.final.txt
├── verifier.verdict
├── retry.events.jsonl                 # when retry runs
├── final.patch
├── final.evaluation.json
└── flow_summary.json
```

These are the primary trajectory artifacts. Judge-friendly extracts are in `evidence/representative-trajectories/`.

## 12. Runtime and cost

Runtime depends heavily on model/provider/network latency, so do not treat wall-clock time as a stable benchmark metric.

Observed deterministic operations were fast:

- pristine dbt build after install: about **3 seconds** in the recorded environment;
- hidden per-case evaluation: typically **single-digit seconds**;
- agentic stages: generally **minutes rather than seconds**.

For planning a clean review, allow roughly **5–10 minutes for setup/downloads after prerequisites**, **a few minutes per single agentic case**, and **up to about an hour for the complete 12-case suite**, depending on provider latency. These are operational estimates, not the primary measured result.

Frozen Iteration-2 resource evidence from OpenCode events:

| Metric | Baseline | DriftGuard |
|---|---:|---:|
| Median tokens / case | 32,493 | 56,475 |
| Total reported cost, 12 cases | 0.09531337 | 0.15752348 |

`reported cost` is the cost field recorded by OpenCode's archived events. Its currency/accounting semantics depend on the configured provider, so the submission reports it as a provider-reported value rather than silently relabeling it.

## 13. Reproduction expectations

Agent outputs are stochastic. Reproduction means another reviewer can:

- create the same 12 incidents;
- verify the same pre-repair control behavior;
- run the same prompts/model configuration;
- compute VRR with the same hidden evaluator;
- inspect complete trajectories and patches.

Exact agent wording/token counts need not be byte-identical. The benchmark injection, oracle, policy gates, and measurement procedure are deterministic.
