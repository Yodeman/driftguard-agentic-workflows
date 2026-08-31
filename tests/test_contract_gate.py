from pathlib import Path
import importlib.util

MODULE_PATH = Path(__file__).resolve().parents[1] / "benchmark" / "contract_gate.py"
spec = importlib.util.spec_from_file_location("contract_gate", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def report(value=True, schema=True, rows=True, build=True, protected=None):
    return {
        "build_pass": build,
        "models": {
            "m": {
                "value_match": value,
                "schema_match": schema,
                "row_count_match": rows,
            }
        },
        "policy": {"protected_upstream_modified": protected or []},
    }


def test_pass_when_contract_equivalent():
    assert mod.decide(report())["decision"] == "PASS"


def test_review_on_value_mismatch():
    x = mod.decide(report(value=False))
    assert x["decision"] == "REVIEW"
    assert "logical_contract_mismatch" in x["reasons"]


def test_review_on_protected_source_edit():
    x = mod.decide(report(protected=["seeds/raw_orders.csv"]))
    assert x["decision"] == "REVIEW"
    assert "protected_upstream_modified" in x["reasons"]


def test_review_on_failed_build():
    assert mod.decide(report(build=False))["decision"] == "REVIEW"
