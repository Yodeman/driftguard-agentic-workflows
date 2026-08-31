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
