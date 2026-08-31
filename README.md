# DriftGuard

**An independent semantic verifier for AI-generated data-pipeline repairs.**

DriftGuard is a hackathon research prototype aimed at one dangerous failure mode: an AI agent repairs a dbt pipeline, the build goes green, but the business data is still wrong.

The project is intentionally benchmark-first. Before adding agent complexity, we create reproducible data-drift incidents and a hidden semantic oracle. The baseline and final workflow must solve the same incidents from the same repository state.

## Current milestone: 3-case feasibility spike

We start with the public `dbt-labs/jaffle_shop_duckdb` project and three incidents:

1. **Orders key rename** — `raw_orders.user_id` becomes `customer_id`.
2. **Payment-method rename** — `raw_payments.payment_method` becomes `method`; the break propagates through staging into both marts.
3. **Payment unit drift** — `raw_payments.amount` changes from cents to dollars while the pipeline still divides by 100. This is the adversarial **green-but-wrong** case.

The key success metric is **Verified Recovery Rate (VRR)**: an incident counts as recovered only when the build succeeds, protected inputs/tests were not modified, and the materialized business outputs match the known-good semantics.

## Why this benchmark is useful

The Jaffle Shop project is self-contained and runs locally on DuckDB. Its current staging payment model converts cents to dollars using `amount / 100`, and its downstream `orders` and `customers` marts aggregate that value. That makes it possible to create a semantic unit-drift incident that can remain syntactically valid while corrupting business metrics.

## Repository layout

```text
benchmark/
  cases/              Incident definitions
  apply_incident.py   Deterministic drift injector
  snapshot.py         Golden/current semantic snapshotter
  evaluate.py         Build + protected-file + semantic evaluation
prompts/
  baseline.md         Fair general-purpose coding-agent prompt
  repair_agent.md     Candidate repair-agent prompt
  verifier_agent.md   Independent verifier prompt draft
scripts/
  bootstrap.sh        Clone/install public dbt benchmark project
  capture_golden.sh   Build pristine repo and capture semantic oracle
  prepare_case.sh     Create a clean incident workspace
  evaluate_case.sh    Score a repaired workspace
CHANGELOG.md           Experiment log template
BENCHMARK.md           Evaluation contract and go/no-go criteria
```

## Quick start

Requires Python 3.13+, Git, and internet access for the one-time bootstrap.

```bash
./scripts/bootstrap.sh
./scripts/capture_golden.sh
./scripts/prepare_case.sh orders_key_rename
```

At that point, give `workspaces/orders_key_rename/` to the baseline coding agent. After it finishes:

```bash
./scripts/evaluate_case.sh orders_key_rename baseline
```

Repeat for:

```bash
./scripts/prepare_case.sh payment_method_rename
./scripts/prepare_case.sh payment_unit_drift
```

Results are appended to `evidence/results.jsonl`.

## Fair-baseline rule

The baseline gets the repository, terminal access, dbt commands, and a normal coding-agent instruction. It does **not** get the private golden snapshot or case oracle. DriftGuard must earn any improvement through purposeful additional evidence/verification rather than a weaker baseline.

## Status

The benchmark harness is scaffolded and locally syntax-tested. This environment did not have outbound Git/PyPI access, so the public dbt repo and dependencies could not be executed here yet. `bootstrap.sh` is designed to make that next step deterministic in a normal clean environment.
