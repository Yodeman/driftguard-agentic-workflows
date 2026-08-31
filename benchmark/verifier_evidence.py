#!/usr/bin/env python3
"""Generate limited, actionable before/after evidence for the verifier agent.

Unlike the hidden evaluator, this report is intended to be shown to the final
workflow. It reveals whether values and schemas changed from a known-good
contract, but it does not reveal raw golden rows or case metadata.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "evidence" / "golden_snapshot.json"


def schema_diff(expected: list[dict], actual: list[dict]) -> list[dict]:
    e = {c["name"]: c["type"] for c in expected}
    a = {c["name"]: c["type"] for c in actual}
    names = sorted(set(e) | set(a))
    return [
        {"column": name, "expected_type": e.get(name), "actual_type": a.get(name)}
        for name in names
        if e.get(name) != a.get(name)
    ]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("repo", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    repo = args.repo.resolve()

    if not GOLDEN.exists():
        raise SystemExit("Golden snapshot missing. Run ./scripts/capture_golden.sh")
    golden = json.loads(GOLDEN.read_text())
    if golden.get("snapshot_version") != 2:
        raise SystemExit("Golden snapshot uses legacy format. Re-run ./scripts/capture_golden.sh")

    build = subprocess.run(["dbt", "build", "--profiles-dir", "."], cwd=repo, text=True, capture_output=True)
    report: dict = {
        "build_pass": build.returncode == 0,
        "purpose": "Independent verifier evidence against the last known-good logical contract",
        "models": {},
    }
    if build.returncode != 0:
        report["build_output_tail"] = (build.stdout + build.stderr)[-3500:]
    else:
        with tempfile.TemporaryDirectory() as td:
            current_path = Path(td) / "current.json"
            snap = subprocess.run(
                [sys.executable, str(ROOT / "benchmark" / "snapshot.py"), str(repo / "jaffle_shop.duckdb"), str(current_path)],
                text=True,
                capture_output=True,
            )
            if snap.returncode != 0:
                raise SystemExit(snap.stderr or snap.stdout)
            current = json.loads(current_path.read_text())

        for model, exp in golden["models"].items():
            act = current["models"].get(model)
            if act is None:
                report["models"][model] = {"missing": True}
                continue
            report["models"][model] = {
                "row_count_match": exp["row_count"] == act["row_count"],
                "expected_row_count": exp["row_count"],
                "actual_row_count": act["row_count"],
                "value_match": exp["values_sha256"] == act["values_sha256"],
                "strict_representation_match": exp["strict_rows_sha256"] == act["strict_rows_sha256"],
                "schema_match": exp["columns"] == act["columns"],
                "schema_diff": schema_diff(exp["columns"], act["columns"]),
            }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
