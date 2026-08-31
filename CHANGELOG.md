# Improvement Changelog

DriftGuard was developed by keeping the same user outcome—**Verified Recovery Rate**—and changing the workflow only when experiment evidence exposed a concrete failure mode.

## Summary

| Stage | What changed | Evidence | Decision / learning |
|---|---|---|---|
| Feasibility control | Built deterministic drift injection + golden semantic oracle on Jaffle Shop | `payment_unit_drift` could pass all 28 dbt resources while payment-derived outputs changed | A green build is not sufficient evidence of recovery; continue. |
| Pilot baseline | General coding agent with repo + terminal + dbt | Structural cases recovered; payment-unit repair restored values but changed monetary output types. Pilot VRR 2/3. | Baseline was already good at obvious drift. Do not add lineage/multi-agent complexity without evidence. Target contract verification instead. |
| Benchmark audit | Blinded workspace names/commit messages; separated value vs schema/contract scoring | Earlier descriptive names leaked incident identity. Hidden evaluator exposed `DOUBLE` → `INTEGER/HUGEINT` contract regression despite green dbt + correct spot checks. | Treat original runs as pilot evidence; harden benchmark before scoring. |
| Iteration 1 — independent verifier | Machine-generated last-known-good contract evidence + fresh semantic verifier + repair retry | Frozen 12-case suite: **6/12 baseline → 7/12 final (50.0% → 58.3%, +8.3 pp)**; 0 regressions. Verifier FAIL precision 100%, recall 66.7%. | Verification helped, but trajectories exposed authority confusion and unsafe repair boundaries. |
| Removed / revised approach — always-on LLM verification | Stopped sending every repair to an LLM verifier | Iteration 1 median workflow tokens were 62,846; many already-correct repairs were being re-reasoned about. | Move provable questions to deterministic code; reserve agent reasoning for unresolved cases. |
| Benchmark preflight experiment | Validated every incident's actual control behavior before spending model calls | Two proposed decimal-ID mutations produced no observable contract change because DuckDB canonicalized them. | Removed those invalid benchmark cases instead of manipulating the evaluator. Final suite remained 12 valid incidents. |
| Iteration 2 — authority + enforcement | Added deterministic contract gate, explicit contract-authority policy, immutable-source guard, bounded compatibility retry | **6/12 baseline → 11/12 final (50.0% → 91.7%, +41.7 pp)**; 5/6 failures rescued; 0 regressions; verifier FAIL precision/recall 100%; 6/12 deterministic gate passes. | Reliability improved most by clarifying authority and enforcing boundaries, not by increasing reasoning. Freeze the official result. |
| Post-hoc infrastructure hardening | Workspace-local scratch policy + detect FAIL→retry-with-no-patch as incomplete execution | The one frozen failure, `order_status_label_swap`, had correct verifier diagnosis but a retry attempted `/tmp`, was auto-rejected by OpenCode, and exited 0 before changing the patch. A later hardened re-run achieved verified recovery. | Process exit success is not task success. Keep official benchmark at 11/12; report later success only as infrastructure validation. |

## Detailed progression

### 0. Feasibility: prove that “green but wrong” exists

The first benchmark version used three deterministic incidents. The critical case, `payment_unit_drift`, changed the upstream representation from cents to dollars while leaving the staging SQL's `amount / 100` conversion in place.

The un-repaired project still completed **28/28 dbt resources successfully**, while `stg_payments`, `orders`, and `customers` no longer matched the known-good logical outputs. That established the user-relevant failure mode: existing tests can be green while business values are wrong.

**Decision:** proceed with an external semantic oracle rather than using `dbt build` as the success metric.

### 1. Pilot baseline: the obvious architecture idea was wrong

A capable general-purpose coding agent repaired both structural rename cases. It also diagnosed the cents→dollars unit change and removed the obsolete division.

Its own checks were persuasive: dbt passed, totals matched, and downstream aggregates looked right. The hidden evaluator nevertheless rejected the result because monetary columns changed from the known-good `DOUBLE` interface to `INTEGER/HUGEINT`.

**Learning:** the failure was not lack of lineage context. It was lack of independent contract verification. We abandoned the planned “add more context / more agents first” direction.

### 2. Benchmark audit: fix leakage before measuring

Pilot trajectories revealed that descriptive workspace names and injected commit messages exposed the incident identity. The benchmark was changed to use opaque workspaces and neutral source-sync commits. Value equality was also separated from schema/interface equality so the evaluator could explain *why* a patch failed.

**Decision:** freeze only blinded runs as scored evidence; retain pilot runs as developmental evidence.

### 3. Iteration 1: independent semantic verification

The workflow added:

1. machine-generated evidence against the last-known-good logical contract;
2. a fresh verifier session that did not generate the candidate patch;
3. a repair retry when the verifier returned FAIL.

**Measured result:**

- Baseline VRR: **6/12 (50.0%)**
- Iteration-1 VRR: **7/12 (58.3%)**
- Improvement: **+8.3 percentage points**
- Regressions: **0**
- Verifier FAIL precision: **100%**
- Verifier FAIL recall: **66.7%**
- Median workflow tokens: **62,846**
- Reported workflow cost total: **0.1779315**

The trajectories exposed two generic failures:

- **Authority confusion:** the verifier sometimes treated “the upstream changed” as sufficient authorization to change downstream business semantics.
- **Unsafe repair boundary:** some retries restored expected outputs by rewriting the upstream source snapshot rather than adapting the downstream staging/model layer.

### 4. Removed/revised experiment: always-on LLM verification

Iteration 1 showed that already-correct candidates were being routed through expensive semantic reasoning. Schema equality, value equality, row counts, and protected-file integrity are not questions that need an LLM when they can be checked exactly.

**Decision:** remove the always-on verifier path. Add a deterministic contract gate and call the semantic verifier only when exact evidence cannot certify the candidate.

### 5. Benchmark preflight: remove invalid cases

Before the 12-case suite was scored, every injection was executed without an agent. Two proposed representation cases—decimal textual encodings of integer IDs—were expected to alter the downstream contract but were canonicalized by DuckDB into the same effective representation.

They were removed and replaced with valid incidents. The final preflight proved:

- 3 structural cases: build fails and contract fails;
- 9 non-structural cases: build succeeds while contract fails.

**Learning:** an adversarial-looking mutation is not automatically a valid benchmark case. Validate the observable contract before using it to measure an agent.

### 6. Iteration 2: explicit authority and enforced boundaries

Iteration 2 added four related mechanisms:

- **Deterministic contract gate:** exact checks certify already-correct repairs without an LLM verifier.
- **Contract-authority policy:** consumer-owned migration/approval evidence can authorize change; otherwise the last-known-good consumer contract remains authoritative. An upstream snapshot alone is not authorization.
- **Immutable-source guard:** retries cannot “repair” the system by rewriting `seeds/*.csv`.
- **Bounded compatibility repair:** verifier FAIL feedback is passed to a fresh repair session that must normalize the new source into the stable consumer contract.

**Frozen measured result:**

| Metric | Baseline | DriftGuard Iteration 2 |
|---|---:|---:|
| Verified Recovery Rate | 6/12 (50.0%) | **11/12 (91.7%)** |
| Absolute change | — | **+41.7 pp** |
| Baseline failures rescued | — | **5** |
| Regressions | — | **0** |
| Verifier FAIL precision | — | **100%** |
| Verifier FAIL recall | — | **100%** |
| Deterministic gate passes | — | **6/12** |
| Semantic verifier calls | — | **6/12** |
| Median tokens | 32,493 | 56,475 |
| Total reported cost | 0.09531337 | 0.15752348 |

This is the official submission result.

### 7. Post-hoc hardening: do not rewrite the frozen score

The one remaining frozen failure was `order_status_label_swap`. The semantic verifier correctly returned FAIL. The retry then attempted a verifier-suggested `/tmp/...` command; OpenCode rejected the external-directory permission request, but the session still exited with code 0 before making a repository change.

The workflow was hardened to:

- translate all scratch operations to `.driftguard/scratch/` inside the workspace;
- detect `verifier=FAIL` + successful process exit + unchanged candidate patch as an incomplete repair attempt;
- allow one bounded completion retry.

A later validation run reached full verified recovery for that case. We deliberately **do not change the official 91.7% result** after inspecting the failure.

## Main failure mode

The main failure mode is **plausible success without contract recovery**: the agent makes a reasonable-looking patch, visible tests pass, and yet business values, interface types, or consumer semantics have silently changed.

A second orchestration-level failure is equally important: an agent process can return exit code 0 without completing the intended state transition. Orchestrators must verify outcomes, not trust process status.

## Hot take

> **Reliable agents need authority boundaries, not just more reasoning. Use deterministic checks for what can be proven, agents for what requires interpretation, and enforcement for constraints the agent must not violate.**
