#!/usr/bin/env python3
"""Capture a stable contract snapshot from the Jaffle Shop DuckDB database.

The snapshot intentionally separates schema stability from value stability:
- strict_rows_sha256 preserves the concrete Python/DuckDB value types.
- values_sha256 canonicalizes numeric values so 10, 10.0, and Decimal('10.00')
  compare as the same business value.

This lets the benchmark distinguish a semantic/value recovery from an interface
schema regression instead of collapsing both into one opaque hash mismatch.
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import hashlib
import json
import math
from pathlib import Path
from typing import Any

DEFAULT_MODELS = ["stg_customers", "stg_orders", "stg_payments", "orders", "customers"]


def normalize_strict(value: Any) -> Any:
    """Preserve representation/type distinctions in the row hash."""
    if value is None:
        return None
    if isinstance(value, bool):
        return {"$bool": value}
    if isinstance(value, int):
        return {"$int": value}
    if isinstance(value, float):
        if math.isnan(value):
            return {"$float": "nan"}
        if math.isinf(value):
            return {"$float": "inf" if value > 0 else "-inf"}
        return {"$float": round(value, 12)}
    if isinstance(value, decimal.Decimal):
        return {"$decimal": format(value.normalize(), "f")}
    if isinstance(value, str):
        return {"$str": value}
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return {"$temporal": value.isoformat()}
    return {"$other": str(value)}


def _canonical_decimal_text(value: int | float | decimal.Decimal) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        dec = decimal.Decimal(str(round(value, 12)))
    else:
        dec = decimal.Decimal(value)
    if dec == 0:
        dec = decimal.Decimal(0)
    text = format(dec.normalize(), "f")
    return text if "." in text else f"{text}.0"


def normalize_value(value: Any) -> Any:
    """Canonicalize by logical value while keeping strings/bools distinct."""
    if value is None:
        return None
    if isinstance(value, bool):
        return {"$bool": value}
    if isinstance(value, (int, float, decimal.Decimal)):
        return {"$num": _canonical_decimal_text(value)}
    if isinstance(value, str):
        return {"$str": value}
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return {"$temporal": value.isoformat()}
    return {"$other": str(value)}


def _hash_rows(rows: list[list[Any]]) -> str:
    encoded = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def snapshot_model(conn, model: str) -> dict:
    schema_rows = conn.execute(f'DESCRIBE SELECT * FROM "{model}"').fetchall()
    columns = [{"name": row[0], "type": row[1]} for row in schema_rows]

    # DuckDB's ORDER BY ALL gives deterministic ordering for these small tables.
    data_rows = conn.execute(f'SELECT * FROM "{model}" ORDER BY ALL').fetchall()
    strict_rows = [[normalize_strict(v) for v in row] for row in data_rows]
    value_rows = [[normalize_value(v) for v in row] for row in data_rows]
    return {
        "columns": columns,
        "row_count": len(data_rows),
        "strict_rows_sha256": _hash_rows(strict_rows),
        "values_sha256": _hash_rows(value_rows),
    }


def capture(database: Path, models: list[str]) -> dict:
    try:
        import duckdb  # type: ignore
    except ImportError as e:
        raise SystemExit("duckdb is not installed. Run scripts/bootstrap.sh first.") from e

    conn = duckdb.connect(str(database), read_only=True)
    try:
        return {
            "snapshot_version": 2,
            "database": database.name,
            "models": {model: snapshot_model(conn, model) for model in models},
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    args = parser.parse_args()

    payload = capture(args.database, args.models)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
