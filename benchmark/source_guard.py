#!/usr/bin/env python3
"""Check/restore immutable upstream-source edits made by a repair agent.

The incident baseline commit already contains the upstream change. Restoring a
protected path to that commit therefore removes only the agent's attempted
source rewrite; it never reverts the injected upstream incident itself.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path

DEFAULT_PROTECTED_GLOBS = ("seeds/*.csv",)


def run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)


def changed_paths(repo: Path, base: str) -> list[str]:
    p = run(repo, "diff", "--name-only", base)
    if p.returncode != 0:
        raise RuntimeError(p.stderr)
    paths = [x.strip() for x in p.stdout.splitlines() if x.strip()]
    u = run(repo, "ls-files", "--others", "--exclude-standard")
    if u.returncode == 0:
        paths.extend(x.strip() for x in u.stdout.splitlines() if x.strip())
    return sorted(set(paths))


def protected(paths: list[str], globs: tuple[str, ...] = DEFAULT_PROTECTED_GLOBS) -> list[str]:
    return sorted(p for p in paths if any(fnmatch.fnmatch(p, g) for g in globs))


def restore(repo: Path, base: str, paths: list[str]) -> None:
    if not paths:
        return
    # `git restore --source <incident-base>` preserves the injected source
    # snapshot while removing the agent's prohibited edits.
    p = run(repo, "restore", "--source", base, "--staged", "--worktree", "--", *paths)
    if p.returncode != 0:
        raise RuntimeError(p.stderr)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("repo", type=Path)
    p.add_argument("base")
    p.add_argument("--restore", action="store_true")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    repo = args.repo.resolve()
    before = changed_paths(repo, args.base)
    violations = protected(before)
    restored = False
    if args.restore and violations:
        restore(repo, args.base, violations)
        restored = True
    after = changed_paths(repo, args.base)
    result = {
        "protected_globs": list(DEFAULT_PROTECTED_GLOBS),
        "violations": violations,
        "violation": bool(violations),
        "restored_to_incident_base": restored,
        "changed_paths_after": after,
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")
    raise SystemExit(1 if violations and not args.restore else 0)


if __name__ == "__main__":
    main()
