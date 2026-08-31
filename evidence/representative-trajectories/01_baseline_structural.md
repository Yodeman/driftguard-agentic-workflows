# Trajectory 1 — Baseline agent solves structural drift

**Case:** `orders_key_rename` (pilot trajectory; later scored runs were blinded)

**Agent:** OpenCode `build`, GLM-5.3-Flash

**Instruction:** investigate the changed dbt project, make the smallest repair, preserve intended behavior, do not revert the upstream source change, and do not weaken tests.

## 1. Inspect source change

The agent inspected the seed diff and found:

```diff
-id,user_id,order_date,status
+id,customer_id,order_date,status
```

It then read `models/staging/stg_orders.sql`, which still contained:

```sql
id as order_id,
user_id as customer_id,
```

## 2. Localize the compatibility boundary

A repository search showed the only executable model reference to the old `user_id` field was in the staging model. The agent chose a one-line boundary repair rather than propagating the source rename through downstream models.

## 3. Patch

```diff
-        user_id as customer_id,
+        customer_id,
```

## 4. Tool retry

The first attempt to call bare `dbt` failed because it was not on PATH. The agent discovered `uv` / project requirements and retried using the uv-managed environment.

This is preserved because trajectories include tool failures and adaptation rather than only the polished final answer.

## 5. Verification

The agent ran dbt seed/build and obtained:

```text
PASS=28 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=28
```

It also checked row counts and sample downstream customer/order values.

## Outcome

The hidden evaluator reported verified recovery. This trajectory establishes that the baseline is a competent coding agent on obvious structural drift; DriftGuard's gains are not created by deliberately weakening the baseline.
