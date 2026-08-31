import decimal
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("snapshot", Path(__file__).parents[1] / "benchmark" / "snapshot.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_numeric_value_canonicalization_equates_representations():
    assert mod.normalize_value(10) == mod.normalize_value(10.0) == mod.normalize_value(decimal.Decimal("10.00"))


def test_strings_are_not_numbers():
    assert mod.normalize_value("10") != mod.normalize_value(10)


def test_strict_keeps_int_float_distinct():
    assert mod.normalize_strict(10) != mod.normalize_strict(10.0)
