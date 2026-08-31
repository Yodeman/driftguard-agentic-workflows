#!/usr/bin/env python3
"""Deterministic first-pass gate for DriftGuard verifier evidence.

The gate answers a narrow question: is the candidate already contract-equivalent
and policy-compliant? If yes, an LLM verifier adds little value and can be
skipped. If not, the case is routed to the semantic verifier.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def decide(report: dict) -> dict:
    models = report.get("models", {})
    model_ok = bool(models) and all(
        (not m.get("missing", False))
        and m.get("row_count_match") is True
        and m.get("value_match") is True
        and m.get("schema_match") is True
        for m in models.values()
    )
    protected = list(report.get("policy", {}).get("protected_upstream_modified", []))
    build_ok = report.get("build_pass") is True
    gate_pass = build_ok and model_ok and not protected

    reasons: list[str] = []
    if not build_ok:
        reasons.append("dbt_build_failed")
    if not model_ok:
        reasons.append("logical_contract_mismatch")
    if protected:
        reasons.append("protected_upstream_modified")

    return {
        "decision": "PASS" if gate_pass else "REVIEW",
        "build_pass": build_ok,
        "contract_equivalent": model_ok,
        "protected_upstream_modified": protected,
        "reasons": reasons,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("evidence", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = decide(json.loads(args.evidence.read_text()))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
