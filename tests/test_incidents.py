from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmark.apply_incident import apply_case

ROOT = Path(__file__).parents[1]


def load_case(name: str) -> dict:
    return json.loads((ROOT / f"benchmark/cases/{name}.json").read_text())


class IncidentTests(unittest.TestCase):
    def repo_with_seed(self, rel: str, text: str):
        td = tempfile.TemporaryDirectory()
        repo = Path(td.name)
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return td, repo, path

    def test_orders_header_rename(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_orders.csv", "id,user_id,order_date,status\n1,7,2020-01-01,placed\n"
        )
        with td:
            apply_case(repo, load_case("orders_key_rename"))
            rows = list(csv.reader(path.read_text().splitlines()))
            self.assertEqual(rows[0], ["id", "customer_id", "order_date", "status"])
            self.assertEqual(rows[1][1], "7")

    def test_payment_method_header_rename(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_payments.csv", "id,order_id,payment_method,amount\n1,2,credit_card,1099\n"
        )
        with td:
            apply_case(repo, load_case("payment_method_rename"))
            self.assertEqual(next(csv.reader(path.read_text().splitlines())), ["id", "order_id", "method", "amount"])

    def test_customer_header_rename(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_customers.csv", "id,first_name,last_name\n1,Ada,Lovelace\n"
        )
        with td:
            apply_case(repo, load_case("customer_key_rename"))
            self.assertEqual(next(csv.reader(path.read_text().splitlines())), ["customer_id", "first_name", "last_name"])

    def test_payment_unit_scale(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_payments.csv",
            "id,order_id,payment_method,amount\n1,2,credit_card,1099\n2,3,coupon,100\n",
        )
        with td:
            apply_case(repo, load_case("payment_unit_drift"))
            rows = list(csv.DictReader(path.read_text().splitlines()))
            self.assertEqual(rows[0]["amount"], "10.99")
            self.assertEqual(rows[1]["amount"], "1.00")

    def test_payment_id_prefixed_representation(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_payments.csv",
            "id,order_id,payment_method,amount\n1,2,credit_card,1099\n2,3,coupon,100\n",
        )
        with td:
            apply_case(repo, load_case("payment_id_prefixed_representation"))
            rows = list(csv.DictReader(path.read_text().splitlines()))
            self.assertEqual([r["id"] for r in rows], ["pay_1", "pay_2"])

    def test_order_date_year_shift(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_orders.csv", "id,user_id,order_date,status\n1,7,2020-01-01,completed\n"
        )
        with td:
            apply_case(repo, load_case("order_date_year_shift"))
            row = next(csv.DictReader(path.read_text().splitlines()))
            self.assertEqual(row["order_date"], "2020-12-31")

    def test_timestamp_representation(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_orders.csv", "id,user_id,order_date,status\n1,7,2020-01-01,completed\n"
        )
        with td:
            apply_case(repo, load_case("order_date_timestamp_representation"))
            row = next(csv.DictReader(path.read_text().splitlines()))
            self.assertEqual(row["order_date"], "2020-01-01 00:00:00")

    def test_payment_method_swap(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_payments.csv",
            "id,order_id,payment_method,amount\n1,1,credit_card,100\n2,2,bank_transfer,200\n3,3,coupon,300\n",
        )
        with td:
            apply_case(repo, load_case("payment_method_label_swap"))
            rows = list(csv.DictReader(path.read_text().splitlines()))
            self.assertEqual([r["payment_method"] for r in rows], ["bank_transfer", "credit_card", "coupon"])

    def test_status_swap(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_orders.csv",
            "id,user_id,order_date,status\n1,1,2020-01-01,completed\n2,2,2020-01-02,returned\n",
        )
        with td:
            apply_case(repo, load_case("order_status_label_swap"))
            rows = list(csv.DictReader(path.read_text().splitlines()))
            self.assertEqual([r["status"] for r in rows], ["returned", "completed"])

    def test_name_padding(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_customers.csv", "id,first_name,last_name\n1,Ada,Lovelace\n"
        )
        with td:
            apply_case(repo, load_case("customer_name_whitespace_drift"))
            row = next(csv.DictReader(path.read_text().splitlines()))
            self.assertEqual(row["first_name"], "  Ada  ")
            self.assertEqual(row["last_name"], "  Lovelace  ")

    def test_cyclic_payment_order_offset(self):
        td, repo, path = self.repo_with_seed(
            "seeds/raw_payments.csv",
            "id,order_id,payment_method,amount\n1,1,credit_card,100\n2,2,coupon,200\n3,3,gift_card,300\n",
        )
        with td:
            apply_case(repo, load_case("payment_order_key_offset"))
            rows = list(csv.DictReader(path.read_text().splitlines()))
            self.assertEqual([r["order_id"] for r in rows], ["2", "3", "1"])

    def test_all_indexed_cases_have_benchmark_metadata(self):
        index = ROOT / "benchmark/cases/index.txt"
        names = [line.strip() for line in index.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(len(names), 12)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            path = ROOT / f"benchmark/cases/{name}.json"
            self.assertTrue(path.exists(), name)
            case = json.loads(path.read_text())
            self.assertEqual(case.get("id"), name)
            self.assertIn(case.get("family"), {"structural", "representation", "silent_semantic"})
            self.assertIn("expected_pre_repair", case)
            self.assertFalse(case["expected_pre_repair"]["contract_pass"])


if __name__ == "__main__":
    unittest.main()
