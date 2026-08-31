# DriftGuard benchmark — v4 expanded suite

## Research question

Can an independent, evidence-grounded verification workflow reduce unsafe AI-generated data-pipeline repairs compared with a fair general-purpose coding-agent baseline?

## Primary metric: Verified Recovery Rate (VRR)

A repairable case counts as a verified recovery only when all of the following hold:

1. `dbt build` succeeds;
2. protected upstream/test inputs are untouched;
3. logical business values match the pristine contract; and
4. the stable logical schema (column names/types and row counts) matches the pristine contract.

`VRR = verified recoveries / total repairable incidents`

The evaluator reports:

- `value_pass`: numeric representations such as `10`, `10.0`, and `10.00` are equal when their business value is equal;
- `schema_pass`: column names/types and row counts match the pristine contract;
- `contract_pass`: both value and schema checks pass;
- `strict_pass`: concrete representation is also identical, retained as diagnostic evidence rather than the primary gate.

## Measured pilot finding

The first three-case pilot established the failure mode that motivated the independent verifier. A general coding agent repaired both simple renames. On `payment_unit_drift`, it correctly found the 100x money error and restored the numeric values, but its patch changed monetary output types from the pristine DOUBLE contract to INTEGER/HUGEINT. Existing dbt tests and the agent's own aggregate checks were green. Independent verifier evidence exposed the remaining schema-contract drift; a retry then achieved full verified recovery.

The original pilot was not blinded enough because descriptive workspace/commit names were visible. Those trajectories are engineering/changelog evidence, not the final headline benchmark.

## Blinding and orchestration controls

Final runs use `scripts/run_opencode_flow.sh`:

- opaque random workspace paths (`workspaces/run_<id>`);
- neutral upstream commit message (`Sync upstream source snapshot`);
- same OpenCode provider/model, `max` variant, repair agent, baseline prompt, tool access, and environment for every case;
- fresh sessions for baseline, verifier, and retry;
- verifier cannot edit the candidate patch;
- verifier evidence is visible only inside `.driftguard/` and excluded from repair metrics;
- raw OpenCode JSONL, exported session, final text, patches, web deep links, and evaluator outputs are archived automatically.

The source Git diff remains visible. That is deliberate: real engineering agents should be allowed to inspect the upstream change. Only benchmark-specific labels/oracles are hidden.

## v4 suite: 12 blinded deterministic incidents

The three-case spike is expanded to twelve cases before reporting a headline improvement number.

| Family | Cases | What it probes |
|---|---:|---|
| Structural | 3 | Obvious schema renames that a competent coding agent should usually recover |
| Representation | 3 | Source encodings/units change while the canonical downstream contract should remain stable |
| Silent semantic | 6 | `dbt build` can remain green while meaning, allocation, dates, or normalized text changes |
| **Total** | **12** | Same golden project and evaluator for every case |

### Structural controls

- `orders_key_rename`: `raw_orders.user_id → customer_id`
- `payment_method_rename`: `raw_payments.payment_method → method`
- `customer_key_rename`: `raw_customers.id → customer_id`

### Representation drift

- `payment_unit_drift`: integer cents become decimal dollars while staging still divides by 100
- `payment_id_prefixed_representation`: payment IDs change from integers to prefixed strings (`1 → pay_1`) while downstream monetary outputs remain executable
- `order_date_timestamp_representation`: date-form source text becomes midnight timestamp-form text

### Silent semantic drift

- `payment_method_label_swap`: two still-valid payment labels swap, so accepted-values tests stay green while payment allocation changes
- `order_status_label_swap`: two still-valid order statuses swap while accepted-values tests stay green
- `customer_name_whitespace_drift`: names gain surrounding whitespace with no existing test failure
- `payment_order_key_offset`: payment order IDs are cyclically re-keyed within a valid observed domain, reallocating money while remaining executable
- `order_customer_key_offset`: order customer IDs are cyclically re-keyed within a valid observed domain, preserving referential validity while reassigning orders
- `order_date_year_shift`: order dates move forward 365 days while the existing test suite remains green

The two key-offset cases are intentionally the hardest in v4. They test whether a repair agent recognizes systematic identifier migration rather than trusting green joins/tests.

The frozen case set is listed explicitly in `benchmark/cases/index.txt`; suite scripts use this manifest so stale/experimental case files cannot silently enter a scored run.

## Preflight before spending model budget

Run:

```bash
./scripts/preflight_suite.sh
```

This prepares each incident without an agent, runs the hidden evaluator, and checks the observed control behavior against case metadata. Structural cases are expected to fail the build; all current representation/silent-semantic cases are designed to build successfully while failing the logical contract. If any case behaves differently on the frozen Jaffle Shop/dbt toolchain, revise or remove it **before** agent evaluation.

## Final experiment

After preflight passes:

```bash
./scripts/run_opencode_suite.sh
```

The suite runs baseline → verifier → conditional retry for each case and then automatically generates:

- `evidence/summary/report.md`
- `evidence/summary/aggregate.json`
- `evidence/summary/latest_runs.csv`
- `evidence/summary/latest_runs.json`

The aggregate report uses the latest completed run per case and reports baseline VRR, final VRR, absolute percentage-point improvement, rescued failures, regressions, verifier verdicts, retry frequency, family-level results, and OpenCode token/cost metadata.

## Decision rule after the 12-case run

Do not add another agent/tool merely because a case fails. First classify the failure trajectory.

- If baseline failures are often rescued by the verifier with few regressions, independent verification is validated as the main contribution.
- If both baseline and DriftGuard fail a coherent family, add the smallest evidence/tool intervention specific to that observed failure and record it as the next changelog iteration.
- If baseline already solves nearly everything, increase semantic difficulty rather than weakening the baseline.
- If the verifier rejects many already-correct patches, prioritize false-rejection reduction before expanding capability.

Ambiguous/abstention cases are intentionally deferred until the repairable-suite scoring is frozen; they require a different safe-resolution metric and should not be mixed into VRR without defining that metric first.

## Iteration-2 verification protocol

The frozen case definitions remain unchanged. Only the solution workflow changes.

For each case:

1. Run the same baseline repair agent and score it with the hidden evaluator.
2. Generate verifier evidence against the last-known-good consumer contract.
3. Run the deterministic contract gate:
   - if build/value/schema/row-count equivalence holds and protected upstream sources are untouched, accept without an LLM verifier;
   - otherwise route to the semantic verifier.
4. The semantic verifier must treat upstream snapshots as observations, not authorization to change consumer semantics. Without explicit consumer-owned migration/approval evidence, unresolved contract drift is a repairable incompatibility.
5. Run one compatibility retry on FAIL.
6. Check immutable upstream sources (`seeds/*.csv`). If the retry modified them, restore only those paths to the incident baseline and allow one bounded policy-correction retry.
7. Run the same hidden evaluator used for the baseline.

Primary metric remains **Verified Recovery Rate (VRR)**. Secondary measurements for this iteration include LLM semantic-verifier call rate, verifier FAIL recall/precision, source-guard violations, policy-retry frequency, tokens, reported cost, and regressions on baseline-success cases.

The Iteration-1 complete 12-case result must be archived before rerunning so the changelog comparison is reproducible.
