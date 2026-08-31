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
