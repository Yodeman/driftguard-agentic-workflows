# DriftGuard feasibility benchmark — v3

## Research question

Can an independent, evidence-grounded verification workflow reduce unsafe AI-generated data-pipeline repairs compared with a fair general-purpose coding-agent baseline?

## Primary metric: Verified Recovery Rate (VRR)

A case is a verified recovery only if:
1. `dbt build` succeeds;
2. protected upstream/test inputs are untouched;
3. logical business values match the pristine contract; and
4. the stable logical schema (column names/types and row counts) matches the pristine contract.

`VRR = verified recoveries / total incidents`

The evaluator now reports the two contract dimensions separately:
- `value_pass`: numeric values are compared canonically, so `10`, `10.0`, and `10.00` are equal as values;
- `schema_pass`: logical column names/types and row counts are unchanged;
- `contract_pass`: both are true.

This prevents a type regression from being mislabeled as a value/semantic failure.

## Pilot finding that motivated v3

The first unblinded pilot produced 2/3 verified recoveries. The coding agent repaired both column-renaming cases. In the payment-unit case it also found the 100x value drift and restored numeric totals, but its patch changed logical amount columns from DOUBLE to INTEGER/HUGEINT. Existing dbt tests passed and the agent's own aggregate checks passed, yet the strict contract oracle rejected the patch.

Because the pilot workspace/commit exposed descriptive case names, those runs are retained as engineering evidence but are not the final benchmark numbers.

## Blinding controls

`prepare_case.sh` now:
- creates an opaque random workspace path (`workspaces/run_<id>`);
- commits the mutated source as `Sync upstream source snapshot`;
- stores case-to-workspace metadata only under `evidence/active/`, outside the agent workspace.

The agent may still inspect the actual upstream Git diff. That is deliberate: a real engineer/agent should be allowed to inspect the source change. We remove only benchmark-specific hints.

## Iteration 1: independent verifier

After a repair candidate, `generate_verifier_evidence.sh CASE_ID` rebuilds the project and emits a limited contract-diff report. The verifier receives this report and the workspace, but not the hidden case definition or golden rows. It must independently investigate discrepancies and return PASS / FAIL / ABSTAIN.

For the pilot payment-unit repair, the expected useful signal is: value equality restored, schema equality not restored. A verifier should reject the candidate and ask the repair agent to preserve the stable amount type as well as its numeric meaning.

## Go/no-go after v3

Proceed to a 12–20 case suite if independent verification fixes/rejects the remaining unsafe candidate while preserving performance on the two straightforward cases. Then add harder semantic cases where value mismatches, not only schema mismatches, survive an ordinary coding-agent self-check.

## Post-pilot expansion plan

The three-case spike validated the harness and exposed a contract-regression failure mode. The next benchmark should grow to at least 12 deterministic incidents before any headline metric is reported. Keep the original three and add cases across four families:

| Family | Target cases | Purpose |
|---|---:|---|
| Structural drift | 3 | Renames/removals that should be straightforward for a competent repair agent |
| Type/representation drift | 3 | Changes that can preserve values while breaking downstream interfaces |
| Silent semantic drift | 4 | Green builds with incorrect business outputs or classifications |
| Ambiguous/unsafe cases | 2 | Cases where the correct action may be to abstain or request human approval |

Use the same frozen model/provider, prompt, tool permissions, and budget for baseline and DriftGuard. Run each case from a newly prepared blinded workspace. Preserve the complete repair and verifier trajectories.
