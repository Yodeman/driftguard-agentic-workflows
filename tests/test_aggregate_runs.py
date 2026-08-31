from pathlib import Path
import importlib.util

MODULE_PATH = Path(__file__).resolve().parents[1] / "benchmark" / "aggregate_runs.py"
spec = importlib.util.spec_from_file_location("aggregate_runs", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_token_total_excludes_cache_accounting():
    assert mod.token_total({"input": 10, "output": 2, "reasoning": 3, "cache_read": 100}) == 15


def test_percent():
    assert mod.percent(2, 3) == 66.7
    assert mod.percent(0, 0) is None
