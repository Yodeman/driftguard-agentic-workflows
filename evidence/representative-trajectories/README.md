# Representative Agent Trajectories

The automated benchmark preserves raw OpenCode events and exports under `evidence/runs/<case>/<run_id>/`. This directory contains concise judge-friendly extracts that demonstrate the three agent roles used by DriftGuard.

| File | Role demonstrated | Why representative |
|---|---|---|
| `01_baseline_structural.md` | General-purpose repair / baseline agent | Shows the baseline is capable and not intentionally weakened. |
| `02_green_but_wrong_payment.md` | Baseline repair + hidden contract evidence + semantic verification need | Shows the core green-but-wrong failure mode. |
| `03_verifier_retry_hard_case.md` | Semantic verifier + retry + orchestration checkpoint | Shows feedback shaping the next step and the post-hoc execution hardening lesson. |

The exact role instructions are committed in `prompts/`:

- baseline: `prompts/baseline.md`
- semantic verifier: `prompts/verifier_agent.md`
- feedback-driven repair: `prompts/repair_retry.md`
- bounded completion retry: `prompts/completion_retry.md`
- policy correction: `prompts/policy_retry.md`

For a submission that includes the actual experiment repository, keep the corresponding raw `.events.jsonl`, `.export.json`, final text, patches, and evaluator JSON alongside these extracts.
