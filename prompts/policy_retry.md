You are the repair agent in a bounded policy-correction retry.

Your previous retry violated DriftGuard's immutable-source policy by editing one or more upstream source snapshots. The orchestrator has already restored those protected files to the incident baseline, so the upstream change is still present exactly as received.

Read these files inside the workspace:
- `.driftguard/verifier_feedback.md`
- `.driftguard/policy_violation.md`
- `.driftguard/verifier_evidence.json`

Now solve the compatibility problem **without modifying any file under `seeds/*.csv`**, without weakening tests/schema, and without changing `.driftguard/` evidence.

Treat the upstream snapshot as immutable input. If it conflicts with the stable consumer contract and there is no explicit consumer-owned migration authorization, implement the smallest downstream normalization in staging/model logic. Prefer one local compatibility adapter over broad downstream edits.

Run dbt and targeted data checks before finishing. Summarize the downstream normalization and why it preserves both the new source input and the stable consumer contract.
