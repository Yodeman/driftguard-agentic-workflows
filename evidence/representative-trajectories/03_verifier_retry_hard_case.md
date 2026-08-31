# Trajectory 3 — Verifier feedback, retry, and execution checkpoint

**Case:** `order_status_label_swap`

This trajectory is included because it shows both the semantic-verifier role and a retry/orchestration failure that shaped the final hardening.

## Frozen Iteration-2 trajectory

1. Baseline repair failed hidden contract recovery.
2. Deterministic gate returned `REVIEW`.
3. The semantic verifier correctly identified the compatibility problem and returned:

```text
DRIFTGUARD_VERDICT: FAIL
```

4. Verifier feedback shaped a fresh repair retry.
5. The retry attempted a falsification/scratch command under `/tmp/...`.
6. OpenCode rejected the external-directory permission request.
7. The agent process still exited with status 0 before applying a repository patch.
8. The hidden evaluator therefore recorded final FAIL.

The key lesson was orchestration-level: **process success is not task success**.

## Post-hoc hardening

Verifier and retry prompts were changed to require scratch operations under:

```text
.driftguard/scratch/
```

The orchestrator also detects:

```text
verifier verdict = FAIL
retry process exit = 0
candidate patch unchanged
```

as an incomplete repair attempt rather than successful completion.

## Validation run after hardening

The later validation flow recorded:

```text
baseline_verified_recovery = false
contract_gate_decision = REVIEW
verifier_mode = semantic_agent
verifier_verdict = FAIL
retry_ran = true
source_guard_violation = false
final_value_pass = true
final_schema_pass = true
final_verified_recovery = true
```

This later run is **not** folded back into the official benchmark score. It is evidence that the generic orchestration hardening addressed the observed runtime interruption.
