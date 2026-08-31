# Evaluation and Evidence

## Evaluation question

Does DriftGuard improve the rate at which AI-generated dbt repairs restore the **actual consumer contract**, not merely a green build, compared with a fair general-purpose coding-agent baseline?

## Primary metric

**Verified Recovery Rate (VRR)**

A case counts only if the repaired project builds and the hidden evaluator confirms the intended values, schema/interface, row counts, and protected-source policy.

## Frozen headline result

| Metric | Baseline | DriftGuard Iteration 2 | Change |
|---|---:|---:|---:|
| Verified recoveries | 6/12 | **11/12** | +5 cases |
| VRR | 50.0% | **91.7%** | **+41.7 pp** |
| Regressions of baseline successes | — | **0** | — |
| Median tokens / case | 32,493 | 56,475 | +23,982 |
| Total provider-reported cost | 0.09531337 | 0.15752348 | +0.06221011 |

Verifier diagnostics in Iteration 2:

- FAIL precision: **100%**
- FAIL recall on baseline failures: **100%**
- PASS specificity: **100%**
- deterministic contract-gate passes: **6/12**
- LLM semantic-verifier calls: **6/12**
- retry runs: **6**
- source-guard violations in the frozen Iteration-2 run: **0**
- regressions: **0**

## Improvement progression

| Stage | VRR | Change vs baseline | Key evidence |
|---|---:|---:|---|
| Baseline | 6/12 = **50.0%** | — | Strong on structural drift, weak on unresolved contract/semantic drift |
| Iteration 1 | 7/12 = **58.3%** | +8.3 pp | Independent verification rescued one failure but recall was only 66.7% |
| Iteration 2 | 11/12 = **91.7%** | **+41.7 pp** | Deterministic gate + authority policy + immutable-source enforcement rescued 5/6 baseline failures |

## Case-level final comparison

| Case | Family | Baseline | Iteration 2 |
|---|---|---:|---:|
| `customer_key_rename` | structural | PASS | PASS |
| `orders_key_rename` | structural | PASS | PASS |
| `payment_method_rename` | structural | PASS | PASS |
| `order_date_timestamp_representation` | representation | PASS | PASS |
| `payment_id_prefixed_representation` | representation | PASS | PASS |
| `payment_unit_drift` | representation | **FAIL** | **PASS** |
| `customer_name_whitespace_drift` | silent semantic | PASS | PASS |
| `order_customer_key_offset` | silent semantic | **FAIL** | **PASS** |
| `order_date_year_shift` | silent semantic | **FAIL** | **PASS** |
| `order_status_label_swap` | silent semantic | **FAIL** | FAIL |
| `payment_method_label_swap` | silent semantic | **FAIL** | **PASS** |
| `payment_order_key_offset` | silent semantic | **FAIL** | **PASS** |

Family-level result:

| Family | Cases | Baseline VRR | Iteration-2 VRR |
|---|---:|---:|---:|
| Structural | 3 | 3/3 (100%) | 3/3 (100%) |
| Representation | 3 | 2/3 (66.7%) | **3/3 (100%)** |
| Silent semantic | 6 | 1/6 (16.7%) | **5/6 (83.3%)** |

## Hard case: `payment_unit_drift`

The upstream source changes payment amounts from cents to dollars while the staging model still divides by 100.

Control state:

```text
dbt build: PASS=28 / 28
business values: wrong
```

The baseline agent correctly diagnosed the unit migration and restored numeric values, but its patch also changed monetary output types from the known-good `DOUBLE` interface to integer-family types. Normal dbt tests and the agent's own value spot-checks passed. The hidden contract evaluator rejected the patch.

The verifier/retry workflow subsequently restored both values and schema/interface, yielding full verified recovery. This case is the clearest demonstration that **build success + plausible data checks can still be insufficient**.

## Challenging remaining case

The frozen Iteration-2 miss was `order_status_label_swap`.

The verifier correctly diagnosed the semantic incompatibility and returned FAIL. The retry attempted an external `/tmp` scratch command, which OpenCode's policy auto-rejected; the agent process nevertheless exited 0 before changing the repository. The frozen evaluator therefore recorded FAIL.

This was treated as a post-hoc infrastructure lesson rather than an excuse to rewrite the score. Workspace-local scratch handling and incomplete-retry detection were added afterward, and a later validation run achieved verified recovery.

**Official result remains 11/12 (91.7%).**

## Evidence references inside a run

For a run directory `evidence/runs/<case>/<run_id>/`:

| Evidence | What it proves |
|---|---|
| `manifest.start.json` | model, variant, OpenCode version, run id, workspace |
| `baseline.events.jsonl` / `baseline.export.json` | baseline trajectory and tools |
| `baseline.evaluation.json` | fair baseline outcome before verifier access |
| `verifier_evidence.json` | machine-generated contract comparison |
| `verifier.events.jsonl` / `verifier.final.txt` | independent verifier reasoning and verdict |
| `candidate_before_verifier.patch` | exact candidate the verifier judged |
| `retry.events.jsonl` | feedback-driven repair trajectory |
| `final.patch` | final repository change |
| `final.evaluation.json` | hidden final VRR gates |
| `flow_summary.json` | compact end-to-end outcome |

Frozen milestone summaries belong under:

```text
evidence/milestones/iteration1/
evidence/milestones/iteration2/
```

The submission package includes compact copies of headline aggregates under `evidence/submission/`.

## Fairness controls

- Same incident cases for baseline and final workflow.
- Same core model/provider/variant and OpenCode agent.
- Baseline runs **before** verifier evidence is generated.
- Incident identity is hidden behind opaque/case-neutral workspaces.
- Source-change commit messages are neutral.
- Hidden golden snapshot is unavailable to the repair agent.
- Every case begins from a fresh incident workspace.
- Preflight validates case behavior before model calls.
- Protected-source and test/schema policies prevent gaming.

## Claims we deliberately do not make

- We do not claim statistical generality beyond this synthetic 12-case benchmark.
- We do not claim 100% official recovery after the post-hoc hardening run.
- We do not claim provider-reported cost is universally comparable across OpenCode providers.
- We do not claim a green dbt build is useless; it remains a necessary lower-level gate.
