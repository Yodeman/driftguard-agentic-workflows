#!/usr/bin/env python3
"""Aggregate latest DriftGuard flow results into submission-ready evidence."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "benchmark" / "cases"
RUNS_DIR = ROOT / "evidence" / "runs"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def stage_usage(run_dir: Path, stage: str) -> dict[str, Any]:
    path = run_dir / f"{stage}.summary.json"
    if not path.exists():
        return {"cost": 0.0, "tokens": {}}
    payload = load_json(path).get("usage_from_stream") or {}
    return {
        "cost": float(payload.get("cost") or 0.0),
        "tokens": payload.get("tokens") or {},
    }


def token_total(tokens: dict[str, Any]) -> int:
    # Keep cache read/write visible separately in the CSV, but this compact
    # workload total uses generated/request tokens rather than double-counting cache.
    return sum(int(tokens.get(k) or 0) for k in ("input", "output", "reasoning"))


def latest_run_summaries() -> list[Path]:
    chosen: list[Path] = []
    if not RUNS_DIR.exists():
        return chosen
    for case_dir in sorted(p for p in RUNS_DIR.iterdir() if p.is_dir()):
        candidates = list(case_dir.glob("run_*/flow_summary.json"))
        if candidates:
            chosen.append(max(candidates, key=lambda p: p.stat().st_mtime_ns))
    return chosen


def percent(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 1) if d else None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, default=ROOT / "evidence" / "summary")
    p.add_argument("--expected-cases", nargs="*", default=None,
                   help="Expected scored case ids. Missing completed flows are reported explicitly.")
    args = p.parse_args()

    rows: list[dict[str, Any]] = []
    for summary_path in latest_run_summaries():
        flow = load_json(summary_path)
        case_id = str(flow["case"])
        case_path = CASES_DIR / f"{case_id}.json"
        case = load_json(case_path) if case_path.exists() else {}
        run_dir = summary_path.parent
        baseline = stage_usage(run_dir, "baseline")
        verifier = stage_usage(run_dir, "verifier")
        retry = stage_usage(run_dir, "retry")
        baseline_tokens = token_total(baseline["tokens"])
        verifier_tokens = token_total(verifier["tokens"])
        retry_tokens = token_total(retry["tokens"])
        rows.append(
            {
                "case": case_id,
                "family": case.get("family", "unknown"),
                "run_id": flow.get("run_id"),
                "model": flow.get("model"),
                "variant": flow.get("variant"),
                "baseline_verified_recovery": bool(flow.get("baseline_verified_recovery")),
                "baseline_value_pass": bool(flow.get("baseline_value_pass")),
                "baseline_schema_pass": bool(flow.get("baseline_schema_pass")),
                "verifier_verdict": flow.get("verifier_verdict"),
                "retry_ran": bool(flow.get("retry_ran")),
                "final_verified_recovery": bool(flow.get("final_verified_recovery")),
                "final_value_pass": bool(flow.get("final_value_pass")),
                "final_schema_pass": bool(flow.get("final_schema_pass")),
                "baseline_tokens": baseline_tokens,
                "verifier_tokens": verifier_tokens,
                "retry_tokens": retry_tokens,
                "workflow_tokens": baseline_tokens + verifier_tokens + retry_tokens,
                "baseline_reported_cost": round(float(baseline["cost"]), 8),
                "workflow_reported_cost": round(float(baseline["cost"] + verifier["cost"] + retry["cost"]), 8),
                "evidence_dir": str(run_dir),
            }
        )

    expected_cases = list(args.expected_cases or [])
    if not expected_cases:
        index = CASES_DIR / "index.txt"
        if index.exists():
            expected_cases = [
                line.strip() for line in index.read_text().splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
    completed_cases = {str(r["case"]) for r in rows}
    missing_cases = [c for c in expected_cases if c not in completed_cases]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "latest_runs.csv"
    json_path = args.output_dir / "latest_runs.json"
    md_path = args.output_dir / "report.md"

    if rows:
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("")
    json_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")

    n = len(rows)
    baseline_ok = sum(r["baseline_verified_recovery"] for r in rows)
    final_ok = sum(r["final_verified_recovery"] for r in rows)
    rescued = sum((not r["baseline_verified_recovery"]) and r["final_verified_recovery"] for r in rows)
    regressions = sum(r["baseline_verified_recovery"] and (not r["final_verified_recovery"]) for r in rows)
    retries = sum(r["retry_ran"] for r in rows)
    verdicts = Counter(str(r["verifier_verdict"]) for r in rows)
    # Treat a baseline verified recovery as a verifier PASS target, and a
    # baseline failure as a FAIL target. ABSTAIN remains neither. This is a
    # useful diagnostic, not the primary user metric.
    verifier_tp = sum((not r["baseline_verified_recovery"]) and r["verifier_verdict"] == "FAIL" for r in rows)
    verifier_fn = sum((not r["baseline_verified_recovery"]) and r["verifier_verdict"] == "PASS" for r in rows)
    verifier_tn = sum(r["baseline_verified_recovery"] and r["verifier_verdict"] == "PASS" for r in rows)
    verifier_fp = sum(r["baseline_verified_recovery"] and r["verifier_verdict"] == "FAIL" for r in rows)
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        families[row["family"]].append(row)

    aggregate = {
        "cases": n,
        "expected_cases": len(expected_cases) if expected_cases else n,
        "complete": not missing_cases and (not expected_cases or n == len(expected_cases)),
        "missing_cases": missing_cases,
        "baseline_verified": baseline_ok,
        "final_verified": final_ok,
        "baseline_vrr_percent": percent(baseline_ok, n),
        "final_vrr_percent": percent(final_ok, n),
        "absolute_vrr_change_pp": round((percent(final_ok, n) or 0) - (percent(baseline_ok, n) or 0), 1) if n else None,
        "baseline_failures_rescued": rescued,
        "regressions": regressions,
        "retry_runs": retries,
        "verifier_verdicts": dict(verdicts),
        "verifier_fail_precision_percent": percent(verifier_tp, verifier_tp + verifier_fp),
        "verifier_fail_recall_percent": percent(verifier_tp, verifier_tp + verifier_fn),
        "verifier_pass_specificity_percent": percent(verifier_tn, verifier_tn + verifier_fp),
        "median_baseline_tokens": int(median([r["baseline_tokens"] for r in rows])) if rows else None,
        "median_workflow_tokens": int(median([r["workflow_tokens"] for r in rows])) if rows else None,
        "total_baseline_reported_cost": round(sum(r["baseline_reported_cost"] for r in rows), 8),
        "total_workflow_reported_cost": round(sum(r["workflow_reported_cost"] for r in rows), 8),
    }
    (args.output_dir / "aggregate.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    suite_status = {
        "complete": aggregate["complete"],
        "expected_cases": expected_cases,
        "completed_cases": sorted(completed_cases),
        "missing_cases": missing_cases,
    }
    (args.output_dir / "suite_status.json").write_text(json.dumps(suite_status, indent=2, sort_keys=True) + "\n")

    lines = [
        "# DriftGuard benchmark report",
        "",
        "> Automatically generated from the latest completed run for each case. Do not use as a final claim until the suite is complete and the run set is frozen.",
        "",
        "## Overall",
        "",
        f"- Suite completeness: **{'COMPLETE' if aggregate['complete'] else 'PARTIAL'}**",
        f"- Cases with completed evidence: **{n}/{aggregate['expected_cases']}**",
        f"- Missing cases: **{', '.join(missing_cases) if missing_cases else 'none'}**",
        f"- Baseline Verified Recovery Rate: **{baseline_ok}/{n} ({percent(baseline_ok, n)}%)**" if n else "- Baseline Verified Recovery Rate: n/a",
        f"- DriftGuard Verified Recovery Rate: **{final_ok}/{n} ({percent(final_ok, n)}%)**" if n else "- DriftGuard Verified Recovery Rate: n/a",
        f"- Absolute change: **{aggregate['absolute_vrr_change_pp']} percentage points**" if n else "- Absolute change: n/a",
        f"- Baseline failures rescued by verification/retry: **{rescued}**",
        f"- Baseline successes regressed by workflow: **{regressions}**",
        f"- Verifier verdicts: **{dict(verdicts)}**",
        f"- Verifier FAIL precision: **{aggregate['verifier_fail_precision_percent']}%**" if n else "- Verifier FAIL precision: n/a",
        f"- Verifier FAIL recall on baseline failures: **{aggregate['verifier_fail_recall_percent']}%**" if n else "- Verifier FAIL recall: n/a",
        f"- Retry stages run: **{retries}/{n}**" if n else "- Retry stages run: n/a",
        "",
        "## By failure family",
        "",
        "| Family | Cases | Baseline VRR | DriftGuard VRR | Rescued | Regressed |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for family in sorted(families):
        fr = families[family]
        fd = len(fr)
        fb = sum(r["baseline_verified_recovery"] for r in fr)
        ff = sum(r["final_verified_recovery"] for r in fr)
        frescue = sum((not r["baseline_verified_recovery"]) and r["final_verified_recovery"] for r in fr)
        freg = sum(r["baseline_verified_recovery"] and (not r["final_verified_recovery"]) for r in fr)
        lines.append(f"| {family} | {fd} | {fb}/{fd} ({percent(fb, fd)}%) | {ff}/{fd} ({percent(ff, fd)}%) | {frescue} | {freg} |")

    lines += [
        "",
        "## Case-level results",
        "",
        "| Case | Family | Baseline | Verifier | Retry | Final | Baseline tokens | Workflow tokens |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for r in sorted(rows, key=lambda x: (x["family"], x["case"])):
        lines.append(
            f"| `{r['case']}` | {r['family']} | {'PASS' if r['baseline_verified_recovery'] else 'FAIL'} | "
            f"{r['verifier_verdict']} | {'yes' if r['retry_ran'] else 'no'} | "
            f"{'PASS' if r['final_verified_recovery'] else 'FAIL'} | {r['baseline_tokens']} | {r['workflow_tokens']} |"
        )

    lines += [
        "",
        "## Resource note",
        "",
        "Token and cost fields are taken from OpenCode's archived step-finish events. Report the frozen model/provider/variant and the benchmark's recorded OpenCode Go usage multiplier alongside any cost claim; do not silently compare them as though baseline and workflow had identical resource budgets.",
        "",
    ]
    md_path.write_text("\n".join(lines))

    print(md_path)
    print(json.dumps(aggregate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
