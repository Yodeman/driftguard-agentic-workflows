# Improvement Changelog

This file intentionally starts before the final system exists. Every meaningful experiment should be recorded, including discarded ideas.

| Stage | What we tried and why | Evidence | Decision / learning |
|---|---|---|---|
| Baseline | General-purpose coding agent with repository + terminal + dbt, no private semantic oracle | **Not run yet** | Establish the fair starting point |
| Iteration 1 | Add structured lineage/blast-radius context | **Not run yet** | Pending |
| Iteration 2 | Add pre/post output-diff evidence | **Not run yet** | Pending |
| Iteration 3 | Add repair-agent self-review | **Not run yet** | Pending; candidate experiment to remove if weak |
| Iteration 4 | Add an independent verifier separated from repair reasoning | **Not run yet** | Pending |
| Iteration 5 | Let verifier propose executable semantic checks grounded in repository evidence | **Not run yet** | Pending |
| Final | Combine only changes with measured benefit | **Not run yet** | Pending |

## Current hypothesized failure mode

A repair agent can optimize for observable build/test success while preserving a mistaken semantic assumption. The `payment_unit_drift` case is designed to test this directly.

## Candidate hot take — not yet a result

> Agents do not necessarily need more reflection; they need external evidence they cannot merely rationalize away.

This should only become a submission claim if the experiments support it.
