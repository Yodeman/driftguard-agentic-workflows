#!/usr/bin/env python3
"""Evaluate one repaired incident against DriftGuard's golden contract."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = Path(__file__).resolve().parent / "cases"
GOLDEN = ROOT / "evidence" / "golden_snapshot.json"
HARNESS_ONLY_PREFIXES = (".driftguard/",)


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def git_changed_paths(repo: Path, base: str) -> list[str]:
    proc = run(["git", "diff", "--name-only", base], repo)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    untracked = run(["git", "ls-files", "--others", "--exclude-standard"], repo)
    if untracked.returncode == 0:
        paths.extend(line.strip() for line in untracked.stdout.splitlines() if line.strip())
    paths = [p for p in paths if not p.startswith(HARNESS_ONLY_PREFIXES)]
    return sorted(set(paths))


def git_numstat(repo: Path, base: str) -> dict:
    proc = run(["git", "diff", "--numstat", base], repo)
    if proc.returncode != 0:
        return {"files": None, "added": None, "deleted": None}
    files = added = deleted = 0
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        files += 1
        if parts[0].isdigit():
            added += int(parts[0])
        if parts[1].isdigit():
            deleted += int(parts[1])
    return {"files": files, "added": added, "deleted": deleted}


def compare_snapshots(golden: dict, current: dict) -> dict:
    schema_mismatches: dict[str, dict] = {}
    value_mismatches: dict[str, dict] = {}
    strict_mismatches: dict[str, dict] = {}

    if golden.get("snapshot_version") != 2:
        raise RuntimeError("Golden snapshot is legacy format. Re-run ./scripts/capture_golden.sh with benchmark v3.")

    for model, expected in golden["models"].items():
        actual = current.get("models", {}).get(model)
        if actual is None:
            schema_mismatches[model] = {"expected": expected.get("columns"), "actual": None}
            value_mismatches[model] = {"expected": expected.get("values_sha256"), "actual": None}
            strict_mismatches[model] = {"expected": expected.get("strict_rows_sha256"), "actual": None}
            continue

        if actual.get("columns") != expected.get("columns") or actual.get("row_count") != expected.get("row_count"):
            schema_mismatches[model] = {
                "expected_columns": expected.get("columns"),
                "actual_columns": actual.get("columns"),
                "expected_row_count": expected.get("row_count"),
                "actual_row_count": actual.get("row_count"),
            }
        if actual.get("values_sha256") != expected.get("values_sha256"):
            value_mismatches[model] = {
                "expected_values_sha256": expected.get("values_sha256"),
                "actual_values_sha256": actual.get("values_sha256"),
            }
        if actual.get("strict_rows_sha256") != expected.get("strict_rows_sha256"):
            strict_mismatches[model] = {
                "expected_strict_rows_sha256": expected.get("strict_rows_sha256"),
                "actual_strict_rows_sha256": actual.get("strict_rows_sha256"),
            }

    schema_pass = not schema_mismatches
    value_pass = not value_mismatches
    strict_pass = not strict_mismatches
    return {
        "schema_pass": schema_pass,
        "value_pass": value_pass,
        "strict_pass": strict_pass,
        "contract_pass": schema_pass and value_pass,
        "schema_mismatches": schema_mismatches,
        "value_mismatches": value_mismatches,
        "strict_mismatches": strict_mismatches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("repo", type=Path)
    parser.add_argument("--system", default="unspecified")
    parser.add_argument("--base", required=True, help="Incident baseline commit SHA")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    case = json.loads((CASES_DIR / f"{args.case}.json").read_text())
    repo = args.repo.resolve()

    started = time.time()
    changed = git_changed_paths(repo, args.base)
    protected_modified = sorted(set(changed) & set(case.get("protected_paths", [])))
    test_modified = sorted(p for p in changed if p.startswith("tests/") or p.endswith("schema.yml"))

    env = os.environ.copy()
    build = run(["dbt", "build", "--profiles-dir", "."], repo, env=env)

    contract = {
        "schema_pass": False,
        "value_pass": False,
        "strict_pass": False,
        "contract_pass": False,
        "schema_mismatches": {"_not_run": "dbt build failed"},
        "value_mismatches": {"_not_run": "dbt build failed"},
        "strict_mismatches": {"_not_run": "dbt build failed"},
    }
    if build.returncode == 0:
        if not GOLDEN.exists():
            raise SystemExit(f"Golden snapshot missing: {GOLDEN}. Run scripts/capture_golden.sh")
        with tempfile.TemporaryDirectory() as td:
            current_path = Path(td) / "current.json"
            snap = run(
                [sys.executable, str(ROOT / "benchmark" / "snapshot.py"), str(repo / "jaffle_shop.duckdb"), str(current_path)],
                ROOT,
                env=env,
            )
            if snap.returncode == 0:
                current = json.loads(current_path.read_text())
                contract = compare_snapshots(json.loads(GOLDEN.read_text()), current)
            else:
                err = snap.stderr or snap.stdout
                contract["schema_mismatches"] = {"_snapshot_error": err}
                contract["value_mismatches"] = {"_snapshot_error": err}
                contract["strict_mismatches"] = {"_snapshot_error": err}

    verified = (
        build.returncode == 0
        and not protected_modified
        and not test_modified
        and contract["contract_pass"]
    )

    result = {
        "evaluator_version": 3,
        "case": args.case,
        "system": args.system,
        "verified_recovery": verified,
        "build_pass": build.returncode == 0,
        "value_pass": contract["value_pass"],
        "schema_pass": contract["schema_pass"],
        "contract_pass": contract["contract_pass"],
        "strict_pass": contract["strict_pass"],
        # Backward-compatible name; now explicitly means full logical contract.
        "semantic_pass": contract["contract_pass"],
        "protected_modified": protected_modified,
        "test_or_schema_modified": test_modified,
        "schema_mismatches": contract["schema_mismatches"],
        "value_mismatches": contract["value_mismatches"],
        "strict_mismatches": contract["strict_mismatches"],
        "diff": git_numstat(repo, args.base),
        "changed_paths": changed,
        "elapsed_evaluation_seconds": round(time.time() - started, 3),
        "dbt_stdout_tail": build.stdout[-4000:],
        "dbt_stderr_tail": build.stderr[-4000:],
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if verified else 1)


if __name__ == "__main__":
    main()
