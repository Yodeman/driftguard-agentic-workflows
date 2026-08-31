#!/usr/bin/env python3
"""Apply one deterministic DriftGuard incident to a Jaffle Shop workspace.

All mutations are source-side changes. The agent is expected to adapt downstream
models without reverting the mutated seed or weakening existing tests.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


def load_case(case_file: Path) -> dict:
    return json.loads(case_file.read_text())


def read_dict_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not fieldnames:
        raise ValueError(f"CSV has no header: {path}")
    return fieldnames, rows


def write_dict_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


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
    fieldnames, rows = read_dict_rows(path)
    if column not in fieldnames:
        raise ValueError(f"Expected column {column!r} not found in {path}: {fieldnames}")

    scale = Decimal(factor)
    quantum = Decimal(1).scaleb(-decimal_places)
    for row in rows:
        try:
            value = Decimal(row[column])
        except (InvalidOperation, KeyError) as e:
            raise ValueError(f"Non-numeric value in {column}: {row.get(column)!r}") from e
        transformed = (value * scale).quantize(quantum, rounding=ROUND_HALF_UP)
        row[column] = format(transformed, f".{decimal_places}f")
    write_dict_rows(path, fieldnames, rows)


def append_time_to_date_column(path: Path, column: str, time_text: str = "00:00:00") -> None:
    fieldnames, rows = read_dict_rows(path)
    if column not in fieldnames:
        raise ValueError(f"Expected column {column!r} not found in {path}: {fieldnames}")
    for row in rows:
        raw = row[column]
        try:
            dt.date.fromisoformat(raw)
        except ValueError as e:
            raise ValueError(f"Expected ISO date in {column}, got {raw!r}") from e
        row[column] = f"{raw} {time_text}"
    write_dict_rows(path, fieldnames, rows)


def swap_csv_values(path: Path, column: str, first: str, second: str) -> None:
    fieldnames, rows = read_dict_rows(path)
    if column not in fieldnames:
        raise ValueError(f"Expected column {column!r} not found in {path}: {fieldnames}")
    seen_first = seen_second = False
    for row in rows:
        value = row[column]
        if value == first:
            row[column] = second
            seen_first = True
        elif value == second:
            row[column] = first
            seen_second = True
    if not seen_first or not seen_second:
        raise ValueError(
            f"Swap requires both values in {path}:{column}; seen {first!r}={seen_first}, {second!r}={seen_second}"
        )
    write_dict_rows(path, fieldnames, rows)


def pad_csv_text_columns(path: Path, columns: list[str], left: str, right: str) -> None:
    fieldnames, rows = read_dict_rows(path)
    missing = [c for c in columns if c not in fieldnames]
    if missing:
        raise ValueError(f"Expected columns missing from {path}: {missing}")
    for row in rows:
        for column in columns:
            row[column] = f"{left}{row[column]}{right}"
    write_dict_rows(path, fieldnames, rows)


def cyclic_offset_csv_integer_column(path: Path, column: str, offset: int) -> None:
    """Shift integer identifiers within their observed domain, wrapping at ends.

    Inferring the observed domain keeps every changed key valid for Jaffle Shop's
    small synthetic datasets while preserving a deterministic, invertible source
    migration that an agent can discover from the upstream diff.
    """
    fieldnames, rows = read_dict_rows(path)
    if column not in fieldnames:
        raise ValueError(f"Expected column {column!r} not found in {path}: {fieldnames}")
    values: list[int] = []
    for row in rows:
        try:
            values.append(int(row[column]))
        except (ValueError, KeyError) as e:
            raise ValueError(f"Expected integer in {column}, got {row.get(column)!r}") from e
    lo, hi = min(values), max(values)
    width = hi - lo + 1
    if width <= 1:
        raise ValueError(f"Cannot cyclically offset degenerate domain {lo}..{hi}")
    for row in rows:
        value = int(row[column])
        shifted = lo + ((value - lo + offset) % width)
        row[column] = str(shifted)
    write_dict_rows(path, fieldnames, rows)




def prefix_csv_column_values(path: Path, column: str, prefix: str) -> None:
    fieldnames, rows = read_dict_rows(path)
    if column not in fieldnames:
        raise ValueError(f"Expected column {column!r} not found in {path}: {fieldnames}")
    for row in rows:
        row[column] = f"{prefix}{row[column]}"
    write_dict_rows(path, fieldnames, rows)


def shift_csv_date_column(path: Path, column: str, days: int) -> None:
    fieldnames, rows = read_dict_rows(path)
    if column not in fieldnames:
        raise ValueError(f"Expected column {column!r} not found in {path}: {fieldnames}")
    delta = dt.timedelta(days=days)
    for row in rows:
        raw = row[column]
        try:
            value = dt.date.fromisoformat(raw)
        except ValueError as e:
            raise ValueError(f"Expected ISO date in {column}, got {raw!r}") from e
        row[column] = (value + delta).isoformat()
    write_dict_rows(path, fieldnames, rows)

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
    elif kind == "append_time_to_date_column":
        append_time_to_date_column(target, mutation["column"], mutation.get("time", "00:00:00"))
    elif kind == "swap_csv_values":
        swap_csv_values(target, mutation["column"], mutation["first"], mutation["second"])
    elif kind == "pad_csv_text_columns":
        pad_csv_text_columns(
            target,
            list(mutation["columns"]),
            mutation.get("left", " "),
            mutation.get("right", " "),
        )
    elif kind == "cyclic_offset_csv_integer_column":
        cyclic_offset_csv_integer_column(target, mutation["column"], int(mutation["offset"]))
    elif kind == "prefix_csv_column_values":
        prefix_csv_column_values(target, mutation["column"], mutation["prefix"])
    elif kind == "shift_csv_date_column":
        shift_csv_date_column(target, mutation["column"], int(mutation["days"]))
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
