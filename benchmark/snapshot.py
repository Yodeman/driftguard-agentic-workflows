#!/usr/bin/env python3
"""Capture a stable semantic snapshot from the Jaffle Shop DuckDB database."""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_MODELS = ["stg_customers", "stg_orders", "stg_payments", "orders", "customers"]


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        # Stable enough for this small deterministic benchmark while tolerating
        # irrelevant binary representation noise.
        return round(value, 12)
    if isinstance(value, decimal.Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    return str(value)


def snapshot_model(conn, model: str) -> dict:
    schema_rows = conn.execute(f'DESCRIBE SELECT * FROM "{model}"').fetchall()
    columns = [{"name": row[0], "type": row[1]} for row in schema_rows]

    # DuckDB's ORDER BY ALL provides deterministic ordering across the small
    # benchmark tables without assuming a particular primary key.
    data_rows = conn.execute(f'SELECT * FROM "{model}" ORDER BY ALL').fetchall()
    normalized = [[normalize(v) for v in row] for row in data_rows]
    encoded = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode()
    return {
        "columns": columns,
        "row_count": len(normalized),
        "rows_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def capture(database: Path, models: list[str]) -> dict:
    try:
        import duckdb  # type: ignore
    except ImportError as e:
        raise SystemExit("duckdb is not installed. Run scripts/bootstrap.sh first.") from e

    conn = duckdb.connect(str(database), read_only=True)
    try:
        return {
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
