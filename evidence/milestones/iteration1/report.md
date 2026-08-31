# DriftGuard benchmark report

> Automatically generated from the latest completed run for each case. Do not use as a final claim until the suite is complete and the run set is frozen.

## Overall

- Suite completeness: **COMPLETE**
- Cases with completed evidence: **12/12**
- Missing cases: **none**
- Baseline Verified Recovery Rate: **6/12 (50.0%)**
- DriftGuard Verified Recovery Rate: **7/12 (58.3%)**
- Absolute change: **8.3 percentage points**
- Baseline failures rescued by verification/retry: **1**
- Baseline successes regressed by workflow: **0**
- Verifier verdicts: **{'PASS': 8, 'FAIL': 4}**
- Verifier FAIL precision: **100.0%**
- Verifier FAIL recall on baseline failures: **66.7%**
- Retry stages run: **4/12**

## By failure family

| Family | Cases | Baseline VRR | DriftGuard VRR | Rescued | Regressed |
|---|---:|---:|---:|---:|---:|
| representation | 3 | 2/3 (66.7%) | 3/3 (100.0%) | 1 | 0 |
| silent_semantic | 6 | 1/6 (16.7%) | 1/6 (16.7%) | 0 | 0 |
| structural | 3 | 3/3 (100.0%) | 3/3 (100.0%) | 0 | 0 |

## Case-level results

| Case | Family | Baseline | Verifier | Retry | Final | Baseline tokens | Workflow tokens |
|---|---|---:|---|---:|---:|---:|---:|
| `order_date_timestamp_representation` | representation | PASS | PASS | no | PASS | 13318 | 30978 |
| `payment_id_prefixed_representation` | representation | PASS | PASS | no | PASS | 51191 | 92269 |
| `payment_unit_drift` | representation | FAIL | FAIL | yes | PASS | 19265 | 67358 |
| `customer_name_whitespace_drift` | silent_semantic | PASS | PASS | no | PASS | 19910 | 46795 |
| `order_customer_key_offset` | silent_semantic | FAIL | FAIL | yes | FAIL | 57871 | 122655 |
| `order_date_year_shift` | silent_semantic | FAIL | PASS | no | FAIL | 26076 | 64411 |
| `order_status_label_swap` | silent_semantic | FAIL | FAIL | yes | FAIL | 37325 | 85239 |
| `payment_method_label_swap` | silent_semantic | FAIL | PASS | no | FAIL | 34533 | 61281 |
| `payment_order_key_offset` | silent_semantic | FAIL | FAIL | yes | FAIL | 31667 | 89434 |
| `customer_key_rename` | structural | PASS | PASS | no | PASS | 19093 | 39575 |
| `orders_key_rename` | structural | PASS | PASS | no | PASS | 8117 | 37975 |
| `payment_method_rename` | structural | PASS | PASS | no | PASS | 15058 | 39717 |

## Resource note

Token and cost fields are taken from OpenCode's archived step-finish events. Report the frozen model/provider/variant and the benchmark's recorded OpenCode Go usage multiplier alongside any cost claim; do not silently compare them as though baseline and workflow had identical resource budgets.
