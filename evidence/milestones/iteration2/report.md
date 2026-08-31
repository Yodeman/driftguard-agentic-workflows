# DriftGuard benchmark report

> Automatically generated from the latest completed run for each case. Do not use as a final claim until the suite is complete and the run set is frozen.

## Overall

- Suite completeness: **COMPLETE**
- Cases with completed evidence: **12/12**
- Missing cases: **none**
- Baseline Verified Recovery Rate: **6/12 (50.0%)**
- DriftGuard Verified Recovery Rate: **11/12 (91.7%)**
- Absolute change: **41.7 percentage points**
- Baseline failures rescued by verification/retry: **5**
- Baseline successes regressed by workflow: **0**
- Verifier verdicts: **{'PASS': 6, 'FAIL': 6}**
- Verifier FAIL precision: **100.0%**
- Verifier FAIL recall on baseline failures: **100.0%**
- Retry stages run: **6/12**
- LLM semantic verifier calls: **6/12**
- Deterministic contract-gate passes: **6/12**
- Verifier PASS→FAIL policy overrides: **0**
- Protected-source guard violations: **0**
- Bounded policy retries: **0**

## By failure family

| Family | Cases | Baseline VRR | DriftGuard VRR | Rescued | Regressed |
|---|---:|---:|---:|---:|---:|
| representation | 3 | 1/3 (33.3%) | 3/3 (100.0%) | 2 | 0 |
| silent_semantic | 6 | 2/6 (33.3%) | 5/6 (83.3%) | 3 | 0 |
| structural | 3 | 3/3 (100.0%) | 3/3 (100.0%) | 0 | 0 |

## Case-level results

| Case | Family | Baseline | Verification mode | Verdict | Retry | Guard | Policy retry | Final | Baseline tokens | Workflow tokens |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| `order_date_timestamp_representation` | representation | PASS | deterministic_contract_gate | PASS | no | clear | no | PASS | 28652 | 28652 |
| `payment_id_prefixed_representation` | representation | FAIL | semantic_agent | FAIL | yes | clear | no | PASS | 53150 | 76037 |
| `payment_unit_drift` | representation | FAIL | semantic_agent | FAIL | yes | clear | no | PASS | 20940 | 64338 |
| `customer_name_whitespace_drift` | silent_semantic | PASS | deterministic_contract_gate | PASS | no | clear | no | PASS | 14650 | 14650 |
| `order_customer_key_offset` | silent_semantic | PASS | deterministic_contract_gate | PASS | no | clear | no | PASS | 48613 | 48613 |
| `order_date_year_shift` | silent_semantic | FAIL | semantic_agent | FAIL | yes | clear | no | PASS | 44115 | 100332 |
| `order_status_label_swap` | silent_semantic | FAIL | semantic_agent | FAIL | yes | clear | no | FAIL | 36559 | 71540 |
| `payment_method_label_swap` | silent_semantic | FAIL | semantic_agent | FAIL | yes | clear | no | PASS | 36334 | 101739 |
| `payment_order_key_offset` | silent_semantic | FAIL | semantic_agent | FAIL | yes | clear | no | PASS | 47089 | 108873 |
| `customer_key_rename` | structural | PASS | deterministic_contract_gate | PASS | no | clear | no | PASS | 16734 | 16734 |
| `orders_key_rename` | structural | PASS | deterministic_contract_gate | PASS | no | clear | no | PASS | 15032 | 15032 |
| `payment_method_rename` | structural | PASS | deterministic_contract_gate | PASS | no | clear | no | PASS | 16096 | 16096 |

## Resource note

Token and cost fields are taken from OpenCode's archived step-finish events. Report the frozen model/provider/variant and the benchmark's recorded OpenCode Go usage multiplier alongside any cost claim; do not silently compare them as though baseline and workflow had identical resource budgets.
