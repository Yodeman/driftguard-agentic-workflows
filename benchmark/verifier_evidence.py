#!/usr/bin/env python3
"""Generate limited, actionable evidence for DriftGuard verification.

The report is intended to be shown to the workflow. It reveals whether current
logical outputs match the last known-good consumer contract and whether the
candidate touched protected upstream sources, but never exposes hidden case
metadata or raw golden rows.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "evidence" / "golden_snapshot.json"
PROTECTED_UPSTREAM_GLOBS = ("seeds/*.csv",)


def schema_diff(expected: list[dict], actual: list[dict]) -> list[dict]:
    e = {c["name"]: c["type"] for c in expected}
    a = {c["name"]: c["type"] for c in actual}
    names = sorted(set(e) | set(a))
    return [
        {"column": name, "expected_type": e.get(name), "actual_type": a.get(name)}
        for name in names
        if e.get(name) != a.get(name)
    ]


def git_changed_paths(repo: Path, base: str | None) -> list[str]:
    if not base:
        return []
    p = subprocess.run(["git", "diff", "--name-only", base], cwd=repo, text=True, capture_output=True)
    if p.returncode != 0:
        return []
    paths = [x.strip() for x in p.stdout.splitlines() if x.strip()]
    u = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo, text=True, capture_output=True)
    if u.returncode == 0:
        paths.extend(x.strip() for x in u.stdout.splitlines() if x.strip())
    return sorted(set(p for p in paths if not p.startswith(".driftguard/")))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("repo", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--base", help="Incident baseline commit; contains the upstream source change")
    args = p.parse_args()
    repo = args.repo.resolve()

    if not GOLDEN.exists():
        raise SystemExit("Golden snapshot missing. Run ./scripts/capture_golden.sh")
    golden = json.loads(GOLDEN.read_text())
    if golden.get("snapshot_version") != 2:
        raise SystemExit("Golden snapshot uses legacy format. Re-run ./scripts/capture_golden.sh")

    changed = git_changed_paths(repo, args.base)
    protected_modified = sorted(
        path for path in changed
        if any(fnmatch.fnmatch(path, pattern) for pattern in PROTECTED_UPSTREAM_GLOBS)
    )

    build = subprocess.run(["dbt", "build", "--profiles-dir", "."], cwd=repo, text=True, capture_output=True)
    report: dict = {
        "evidence_version": 2,
        "build_pass": build.returncode == 0,
        "purpose": "Independent evidence against the last known-good consumer logical contract",
        "models": {},
        "candidate_changed_paths": changed,
        "policy": {
            "contract_authority": "last_known_good_consumer_contract",
            "default_action_on_mismatch": "preserve_contract_unless_explicit_consumer_owned_migration_evidence_authorizes_change",
            "upstream_snapshot_is_observation_not_authorization": True,
            "protected_upstream_globs": list(PROTECTED_UPSTREAM_GLOBS),
            "protected_upstream_modified": protected_modified,
            "human_contract_change_approval_present": False,
        },
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
