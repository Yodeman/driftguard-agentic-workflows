# Trajectory 2 — Green build, plausible repair, hidden contract regression

**Case:** `payment_unit_drift`

## 1. Incident and visible behavior

Upstream payment amounts changed from cents to dollars:

```text
1000 -> 10.00
2000 -> 20.00
```

The staging model still contained:

```sql
-- amount is stored in cents, so convert it to dollars
amount / 100 as amount
```

Before repair, dbt still completed all 28 resources successfully. Direct inspection showed values such as:

```text
raw payment 1:       10
stg payment 1:       0.1
order 1 amount:      0.1
customer 1 lifetime: 0.33
```

This is the core green-but-wrong incident.

## 2. Baseline repair agent

The baseline correctly inferred the unit migration and changed staging to pass the upstream amount through:

```diff
-        amount / 100 as amount
+        amount
```

It ran dbt successfully and performed reasonable semantic spot checks:

```text
sum(stg_payments.amount) == sum(raw_payments.amount) == 1672
orders aggregate mismatches: 0
customer lifetime value mismatches: 0
```

The agent concluded that the repair was correct.

## 3. Hidden evaluator feedback

The candidate restored business values but changed the logical monetary interface. Examples observed by the evaluator included:

```text
stg_payments.amount: expected DOUBLE, candidate INTEGER
orders.amount:       expected DOUBLE, candidate HUGEINT
customer_lifetime_value: expected DOUBLE, candidate HUGEINT
```

So:

```text
build_pass = true
value behavior = plausibly repaired
contract/schema = not preserved
verified_recovery = false
```

This was the key evidence that motivated independent contract verification.

## 4. Independent verifier / retry outcome

In the verifier workflow, machine evidence exposed the remaining contract mismatch to a fresh verifier rather than asking the repair agent to judge its own work. The verifier rejected the candidate, a fresh repair retry preserved both values and interface, and the final evaluator reported:

```text
build_pass = true
value_pass = true
schema_pass = true
contract_pass = true
verified_recovery = true
```

## Learning

A repair agent can perform good investigation, run meaningful data checks, and still miss a compatibility regression. “More self-review” is not equivalent to independent evidence against a stable consumer contract.
