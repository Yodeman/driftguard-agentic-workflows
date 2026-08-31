# Improvement Changelog

| Stage | What we tried and why | Evidence | Decision / learning |
|---|---|---|---|
| Pilot baseline | General-purpose coding agent with repository + terminal + dbt, no private golden contract | `orders_key_rename`: verified recovery. `payment_method_rename`: verified recovery. `payment_unit_drift`: build passed and values were repaired, but the hidden contract evaluator rejected output-type regressions. Pilot VRR = 2/3. | Baseline is strong on obvious structural drift. Do not add lineage/context merely because it was planned. Investigate the concrete remaining failure. |
| Benchmark audit | Reviewed trajectories for leakage and decomposed semantic vs schema failure | Descriptive workspace names/commit messages leaked incident identity. The payment-unit repair also changed `DOUBLE` monetary interfaces to `INTEGER/HUGEINT` while all dbt tests and value spot checks passed. | Harden benchmark with opaque workspace ids, neutral upstream commit, numeric value canonicalization, and separate value/schema/contract scoring. Treat original three runs as pilot evidence. |
| Iteration 1 — independent contract verifier | Generate limited machine evidence from the last-known-good logical contract, let an independent verifier reject unsafe repairs, then allow a repair retry | On the blinded `payment_unit_drift` workflow, the final `driftguard_v1` evaluation achieved `build_pass=true`, `value_pass=true`, `schema_pass=true`, `contract_pass=true`, `strict_pass=true`, and `verified_recovery=true`; no tests/schema files or protected paths were modified. | **Keep.** This is the first measured successful DriftGuard intervention. It restored both business values and the interface contract. Re-run across a larger blinded suite before claiming an overall improvement rate. |
| Harness hygiene | Prevent verifier evidence from appearing as a repair artifact | v3.1 stores verifier evidence under `.driftguard/` inside the agent workspace and excludes harness-only paths from repair diffs, while retaining an archival copy under `evidence/`. | Keep evaluation evidence separate from production changes so changed-file metrics remain interpretable. |
| Iteration 2 — executable semantic checks | Add verifier-generated checks for harder value-semantic mismatches that schema comparison alone cannot explain | **Pending larger benchmark** | Only keep if it improves silent-semantic cases without materially increasing false rejection. |
| Final | Combine only measured improvements | **Pending 12+ case evaluation** | Pending. |

## Evidence-backed failure mode

A repair agent can pass the full dbt suite and even validate correct aggregate values while still changing the downstream interface contract. In the pilot `payment_unit_drift` repair, removing `/ 100` corrected the money values but also removed an implicit numeric coercion, producing `INTEGER/HUGEINT` outputs where the pristine interface used `DOUBLE`.

The blinded DriftGuard retry subsequently recovered both values and schema contract, reaching full verified recovery.

## Current hot-take candidate

> Reliable repair agents need independent contract evidence, not just more self-review: green tests and correct spot checks can still hide compatibility regressions.

This is supported by the pilot and one blinded DriftGuard recovery, but should only become the submission's headline insight after the expanded evaluation reproduces the effect across multiple cases.

## Iteration 1b — automate the OpenCode experiment protocol

**What changed:** Replaced manual OpenCode TUI handoffs with a reproducible shell orchestrator built around `opencode run`. The runner fixes GLM-5.3-Flash, `max` variant, fresh sessions, the same Build agent for repair attempts, in-workspace `.driftguard/` evidence handoff, automatic verifier verdict routing, and trajectory/session export.

**Why:** Manual copying of verifier evidence solved permissions locally but introduced avoidable operator variance and made large benchmark runs tedious. The automation makes the exact baseline → verifier → retry boundary reproducible and preserves submission-ready trajectories automatically.

**Decision:** Use the automated runner for all future benchmark measurements. Retain the earlier manual run as pilot evidence, not the final aggregate evaluation.

### Infrastructure iteration — Web project routing + robust verifier parsing (v3.4)

**Observed failure:** OpenCode Web could launch successfully while showing no projects/sessions on Home even though attached `opencode run` stages were active in the terminal. The verifier router was also brittle when a valid verdict was formatted as Markdown such as `# Fail`.

**What changed:** Single-case flows now prepare the blinded workspace before auto-starting Web so the managed server starts in that workspace. More importantly, each OpenCode stage watches its JSONL stream for the session id, builds the Web app's directory-scoped direct session route, persists it as `<stage>.web_url.txt`, and best-effort opens it. The suite starts the managed Web server from its first case workspace and relies on direct links for later cases. Verifier output now prefers `DRIFTGUARD_VERDICT: ...` but also safely parses Markdown headings/emphasis, explicit verdict labels, and JSON; conflicting markers fail closed.

**Evidence/decision:** Added unit coverage for `# Fail`, bold verdicts, labels, JSON, non-verdict prose, conflicting markers, and session deep-link generation. Keep this as benchmark infrastructure; it does not alter agent capabilities or hidden evaluation.

### Infrastructure iteration — OpenCode Web attachment (v3.3)

**What changed:** Routed scripted baseline, verifier, and retry sessions through
a persistent `opencode web` backend using `opencode run --attach`. Added a
server lifecycle helper and suite-level server reuse.

**Why:** Raw JSONL/export trajectories are ideal evidence artifacts but slow to
inspect during experiments. OpenCode Web provides a readable live view of the
same sessions without changing the agent model or experimental protocol.

**Experimental interpretation:** This is an observability/reproducibility
improvement, not an agent-quality intervention, so it must not be credited as a
performance gain in the improvement evaluation.

## Iteration — benchmark expansion to 12 blinded cases

**Why:** The successful `payment_unit_drift` verifier/retry result validated one designed failure mode, but continuing to optimize that case would overfit the solution. The benchmark was expanded before adding new agent capabilities.

**What changed:** Added 9 new deterministic incidents for a 12-case suite across structural, representation, and silent-semantic drift. Added a no-agent preflight that verifies each incident behaves as designed on the frozen environment, plus automatic suite aggregation for baseline/final VRR, rescued failures, regressions, verdicts, and resource metadata.

**Decision:** Freeze the agent architecture during the first 12-case run. Use observed family-level failures to choose the next intervention, if any. Ambiguous/abstention cases are deferred until a separate safe-resolution metric is defined so they do not contaminate VRR.


### Benchmark revision v4.1 — remove seed-inference no-ops

**Observed failure:** Preflight showed that `customer_id_decimal_representation` and `payment_order_id_decimal_representation` remained `contract_pass=true`. dbt/DuckDB canonicalized decimal-form identifier text such as `1.0` back to the same effective integer representation, so those mutations did not create real incidents on the frozen toolchain.

**Decision:** Removed both ineffective cases before any model-budget runs. Replaced them with `payment_id_prefixed_representation` (a green-build representation drift) and `order_date_year_shift` (a green-build silent semantic drift). The suite remains 12 cases, now 3 structural / 3 representation / 6 silent-semantic.
