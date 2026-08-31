from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.apply_incident import apply_case


class IncidentTests(unittest.TestCase):
    def test_orders_header_rename(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "seeds").mkdir()
            path = repo / "seeds/raw_orders.csv"
            path.write_text("id,user_id,order_date,status\n1,7,2020-01-01,placed\n")
            case = json.loads((Path(__file__).parents[1] / "benchmark/cases/orders_key_rename.json").read_text())
            apply_case(repo, case)
            with path.open() as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], ["id", "customer_id", "order_date", "status"])
            self.assertEqual(rows[1][1], "7")

    def test_payment_method_header_rename(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "seeds").mkdir()
            path = repo / "seeds/raw_payments.csv"
            path.write_text("id,order_id,payment_method,amount\n1,2,credit_card,1099\n")
            case = json.loads((Path(__file__).parents[1] / "benchmark/cases/payment_method_rename.json").read_text())
            apply_case(repo, case)
            with path.open() as f:
                header = next(csv.reader(f))
            self.assertEqual(header, ["id", "order_id", "method", "amount"])

    def test_payment_unit_scale(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "seeds").mkdir()
            path = repo / "seeds/raw_payments.csv"
            path.write_text("id,order_id,payment_method,amount\n1,2,credit_card,1099\n2,3,coupon,100\n")
            case = json.loads((Path(__file__).parents[1] / "benchmark/cases/payment_unit_drift.json").read_text())
            apply_case(repo, case)
            with path.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["amount"], "10.99")
            self.assertEqual(rows[1]["amount"], "1.00")


if __name__ == "__main__":
    unittest.main()
