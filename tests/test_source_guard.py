from pathlib import Path
import importlib.util
import subprocess

MODULE_PATH = Path(__file__).resolve().parents[1] / "benchmark" / "source_guard.py"
spec = importlib.util.spec_from_file_location("source_guard", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)


def test_guard_detects_and_restores_only_seed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "seeds").mkdir()
    (repo / "models").mkdir()
    (repo / "seeds/raw.csv").write_text("id\n1\n")
    (repo / "models/a.sql").write_text("select 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "incident baseline")
    base = git(repo, "rev-parse", "HEAD").stdout.strip()

    (repo / "seeds/raw.csv").write_text("id\n2\n")
    (repo / "models/a.sql").write_text("select 2\n")
    paths = mod.changed_paths(repo, base)
    assert mod.protected(paths) == ["seeds/raw.csv"]
    mod.restore(repo, base, ["seeds/raw.csv"])
    assert (repo / "seeds/raw.csv").read_text() == "id\n1\n"
    assert (repo / "models/a.sql").read_text() == "select 2\n"
