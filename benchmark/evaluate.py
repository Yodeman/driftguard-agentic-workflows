#!/usr/bin/env python3
"""Evaluate one repaired incident workspace against DriftGuard's golden semantics."""

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
    mismatches = {}
    for model, expected in golden["models"].items():
        actual = current.get("models", {}).get(model)
        if actual != expected:
            mismatches[model] = {"expected": expected, "actual": actual}
    return {"pass": not mismatches, "mismatches": mismatches}


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
    # Use the repository-local profiles.yml, which the public DuckDB project ships with.
    build = run(["dbt", "build", "--profiles-dir", "."], repo, env=env)

    semantic = {"pass": False, "mismatches": {"_not_run": "dbt build failed"}}
    current_snapshot = None
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
                current_snapshot = json.loads(current_path.read_text())
                semantic = compare_snapshots(json.loads(GOLDEN.read_text()), current_snapshot)
            else:
                semantic = {"pass": False, "mismatches": {"_snapshot_error": snap.stderr or snap.stdout}}

    verified = (
        build.returncode == 0
        and not protected_modified
        and not test_modified
        and semantic["pass"]
    )

    result = {
        "case": args.case,
        "system": args.system,
        "verified_recovery": verified,
        "build_pass": build.returncode == 0,
        "semantic_pass": semantic["pass"],
        "protected_modified": protected_modified,
        "test_or_schema_modified": test_modified,
        "semantic_mismatches": semantic["mismatches"],
        "diff": git_numstat(repo, args.base),
        "changed_paths": changed,
        "elapsed_evaluation_seconds": round(time.time() - started, 3),
        "dbt_stdout_tail": build.stdout[-4000:],
        "dbt_stderr_tail": build.stderr[-4000:],
    }

    output = args.output
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if verified else 1)


if __name__ == "__main__":
    main()
