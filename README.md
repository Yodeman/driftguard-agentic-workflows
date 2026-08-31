# DriftGuard v3

**Independent contract verification for AI-generated dbt repairs.**

This v3 package incorporates the first real baseline experiment. The baseline was strong enough to solve obvious drift and even detect the payment-unit change, which exposed two benchmark-design lessons: the original case names leaked hints, and the evaluator conflated value mismatches with type/interface mismatches.

v3 fixes both issues and makes the next experiment evidence-driven.

## Setup

```bash
./scripts/bootstrap.sh
./scripts/capture_golden.sh
```

`capture_golden.sh` must be re-run because v3 uses snapshot format 2 with separate value and schema hashes.

## Run a blinded baseline case

```bash
./scripts/prepare_case.sh payment_unit_drift
```

The script prints an opaque `workspaces/run_<id>` path. Give **only that workspace** plus `prompts/baseline.md` to the coding agent.

After the agent finishes:

```bash
./scripts/evaluate_case.sh payment_unit_drift baseline_v3
```

## Run Iteration 1: independent verifier

On the same repaired candidate workspace:

```bash
./scripts/generate_verifier_evidence.sh payment_unit_drift
```

Give the generated verifier-evidence JSON, the same workspace, and `prompts/verifier_agent.md` to a fresh verifier-agent session. The verifier must not edit the project.

If verdict is FAIL/ABSTAIN, give its feedback to a fresh repair-agent session using `prompts/repair_retry.md`. Then re-evaluate:

```bash
./scripts/evaluate_case.sh payment_unit_drift driftguard_v1
```

For a clean final comparison, repeat the same flow on all three cases after v3 blinding is enabled.

### v3.1 verifier-evidence hygiene

`generate_verifier_evidence.sh` now writes an archival report under `evidence/` and a verifier-visible copy at `.driftguard/verifier_evidence.json` inside the blinded workspace. `.driftguard/` is excluded from git repair diffs, so harness metadata does not inflate changed-file metrics. The evaluator also ignores this harness-only prefix defensively.

## v3.2: automated OpenCode orchestration

The benchmark can now drive the complete repair → verify → retry loop itself using OpenCode's non-interactive CLI.

The default configuration matches the frozen experimental setup:

- model: auto-detect the unique `*/glm-5.3-flash` entry from `opencode models`;
- variant / reasoning effort: `max`;
- primary agent: OpenCode `build`;
- OpenCode Go usage multiplier: recorded as `2x` metadata (it does not alter the CLI request);
- every baseline, verifier, and retry invocation starts a **fresh OpenCode session**;
- the pinned DriftGuard Python/dbt environment is put on `PATH` for every stage;
- verifier evidence and retry feedback are copied into `.driftguard/` inside the blinded workspace, so agents never need permission to read outside it;
- `.driftguard/` is excluded from repair diffs;
- the verifier candidate patch/status is snapshotted before and after verification. If the verifier edits the candidate, the flow stops as a protocol violation.

Run one full case:

```bash
./scripts/run_opencode_flow.sh payment_unit_drift
```

Run all currently defined benchmark cases:

```bash
./scripts/run_opencode_suite.sh
```

Or specify a subset:

```bash
./scripts/run_opencode_suite.sh orders_key_rename payment_unit_drift
```

### OpenCode configuration overrides

If multiple providers expose GLM-5.3-Flash, set the exact model returned by `opencode models`:

```bash
export DRIFTGUARD_OPENCODE_MODEL='provider/glm-5.3-flash'
```

Other supported overrides:

```bash
export DRIFTGUARD_OPENCODE_VARIANT=max
export DRIFTGUARD_OPENCODE_AGENT=build
export DRIFTGUARD_OPENCODE_VERIFIER_AGENT=build
export DRIFTGUARD_OPENCODE_USAGE_MULTIPLIER=2
export DRIFTGUARD_RETRY_ON_ABSTAIN=0
```

`ABSTAIN` is treated as a human-review outcome by default. Set `DRIFTGUARD_RETRY_ON_ABSTAIN=1` only for experiments where you intentionally want the repair agent to take another attempt after verifier uncertainty.

The flow stores a complete evidence bundle under:

```text
evidence/runs/<case>/<run_id>/
```

including raw OpenCode JSONL events, session exports when available, final agent messages, verifier verdict, candidate/final patches, baseline/final evaluator JSON, and `flow_summary.json`.

## v3.4: resilient OpenCode Web trajectories and verdict parsing

Automated benchmark runs now attach every OpenCode stage to one persistent local
OpenCode Web server. This preserves the scripted `baseline -> verifier -> retry`
protocol while making the live tool calls, messages, and session history easy to
inspect in a browser.

OpenCode's supported architecture for this is:

- `opencode web` starts the browser UI and backend server;
- `opencode run --attach <url>` runs a non-interactive scripted session against
  that same backend;
- baseline, verifier, and retry remain separate fresh sessions, each titled with
  its stage and DriftGuard run id.

DriftGuard defaults to a local-only web server at `http://127.0.0.1:4096` and
starts it automatically when the first flow begins. The helper starts the server
with DriftGuard's pinned `.venv/bin` on `PATH`, which matters because attached
agent tools execute in the server process environment.

Run normally:

```bash
./scripts/run_opencode_flow.sh payment_unit_drift
```

The flow now prepares the blinded workspace before auto-starting OpenCode Web,
so a single-case server starts with that workspace as its process working
directory. Each agent stage still uses `opencode run --attach ... --dir <workspace>`.

OpenCode Web has had frontend versions where CLI-created sessions exist on the
backend but the Home/sidebar does not automatically register the associated
project. DriftGuard therefore does not rely on Home. As soon as the raw OpenCode
event stream exposes the new session id, the runner creates a direct project/session
web URL, prints it, saves it as `<stage>.web_url.txt`, and best-effort opens it in
the browser. This makes baseline, verifier, and retry trajectories directly
viewable even when the Home page is empty.

To print links without opening browser tabs:

```bash
export DRIFTGUARD_OPENCODE_WEB_OPEN_SESSION=0
```

Manage the server explicitly when useful:

```bash
./scripts/opencode_web.sh start
./scripts/opencode_web.sh status
./scripts/opencode_web.sh stop
```

A suite shares one web backend across all cases. If DriftGuard owns the server,
the first case starts it from that case's blinded workspace; later cases reuse
the backend and expose their own direct session links:

```bash
./scripts/run_opencode_suite.sh
```

The server is intentionally left running after a flow/suite so trajectories can
be reviewed. Stop it when finished with `./scripts/opencode_web.sh stop`.

### Web configuration overrides

```bash
# Disable browser-backed execution and use standalone `opencode run` behavior.
export DRIFTGUARD_OPENCODE_WEB=0

# Use another local port/host for a DriftGuard-managed server.
export DRIFTGUARD_OPENCODE_WEB_HOST=127.0.0.1
export DRIFTGUARD_OPENCODE_WEB_PORT=4096

# Require a pre-started server instead of auto-starting one.
export DRIFTGUARD_OPENCODE_WEB_AUTOSTART=0
export DRIFTGUARD_OPENCODE_WEB_URL=http://127.0.0.1:4096
```

If `DRIFTGUARD_OPENCODE_WEB_URL` is set, DriftGuard treats that server as
external and will not stop it. For benchmark reproducibility, prefer the helper
so the server inherits the frozen dbt/Python environment.

The default `127.0.0.1` binding is local-only. If you deliberately expose
OpenCode on a network interface, set `OPENCODE_SERVER_PASSWORD` (and optionally
`OPENCODE_SERVER_USERNAME`) before starting it.

`manifest.start.json` and `flow_summary.json` record whether web attachment was
enabled and the server URL. `flow_summary.json` also includes the direct web URL
for each stage when available. Passwords are never written to benchmark evidence.

### Verifier verdict robustness

The verifier prompt now requests a machine-readable marker such as
`DRIFTGUARD_VERDICT: FAIL`, but orchestration does not depend on perfect formatting.
The parser also accepts common variants including `# Fail`, `**PASS**`,
`Verdict: ABSTAIN`, and a JSON `verdict` field. It does not search arbitrary prose
for verdict words, and conflicting explicit markers fail closed instead of being
guessed. This keeps formatting variation from accidentally changing benchmark
control flow.
