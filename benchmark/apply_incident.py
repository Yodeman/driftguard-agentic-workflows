#!/usr/bin/env python3
"""Apply one deterministic DriftGuard incident to a Jaffle Shop workspace."""

from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


def load_case(case_file: Path) -> dict:
    return json.loads(case_file.read_text())


def rename_csv_column(path: Path, old: str, new: str) -> None:
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    header = rows[0]
    if old not in header:
        raise ValueError(f"Expected column {old!r} not found in {path}: {header}")
    if new in header:
        raise ValueError(f"Target column {new!r} already exists in {path}: {header}")
    header[header.index(old)] = new
    with path.open("w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def scale_csv_numeric_column(path: Path, column: str, factor: str, decimal_places: int) -> None:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames or column not in fieldnames:
            raise ValueError(f"Expected column {column!r} not found in {path}: {fieldnames}")
        rows = list(reader)

    scale = Decimal(factor)
    quantum = Decimal(1).scaleb(-decimal_places)
    for row in rows:
        try:
            value = Decimal(row[column])
        except (InvalidOperation, KeyError) as e:
            raise ValueError(f"Non-numeric value in {column}: {row.get(column)!r}") from e
        transformed = (value * scale).quantize(quantum, rounding=ROUND_HALF_UP)
        row[column] = format(transformed, f".{decimal_places}f")

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def apply_case(repo: Path, case: dict) -> None:
    mutation = case["mutation"]
    target = repo / mutation["path"]
    if not target.exists():
        raise FileNotFoundError(target)

    kind = mutation["kind"]
    if kind == "rename_csv_column":
        rename_csv_column(target, mutation["from"], mutation["to"])
    elif kind == "scale_csv_numeric_column":
        scale_csv_numeric_column(
            target,
            mutation["column"],
            mutation["factor"],
            int(mutation.get("decimal_places", 2)),
        )
    else:
        raise ValueError(f"Unknown mutation kind: {kind}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", help="Case id, e.g. payment_unit_drift")
    parser.add_argument("repo", type=Path, help="Path to Jaffle Shop workspace")
    args = parser.parse_args()

    case_file = Path(__file__).parent / "cases" / f"{args.case}.json"
    if not case_file.exists():
        raise SystemExit(f"Unknown case: {args.case}")
    case = load_case(case_file)
    apply_case(args.repo.resolve(), case)
    print(json.dumps({"case": case["id"], "repo": str(args.repo.resolve()), "applied": True}))


if __name__ == "__main__":
    main()
