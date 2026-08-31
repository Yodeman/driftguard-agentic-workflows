#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor/jaffle_shop_duckdb"
VENV="$ROOT/.venv"
PYTHON_VERSION="${DRIFTGUARD_PYTHON:-3.13}"

command -v uv >/dev/null 2>&1 || {
  echo "uv is required but was not found on PATH." >&2
  echo "Install uv first, then re-run ./scripts/bootstrap.sh" >&2
  exit 2
}

if [[ ! -d "$VENDOR/.git" ]]; then
  rm -rf "$VENDOR"
  git clone --branch duckdb --depth 1 https://github.com/dbt-labs/jaffle_shop_duckdb.git "$VENDOR"
fi

# Recreate the benchmark environment on every bootstrap. This prevents an
# older .venv (for example Python 3.12) from being silently reused when the
# benchmark selector is Python 3.13.
rm -rf "$VENV"
uv venv --python "$PYTHON_VERSION" "$VENV"

# Install the benchmark dependencies with uv rather than pip.
uv pip install --python "$VENV/bin/python" -r "$VENDOR/requirements.txt"

UV_RUN=(uv run --no-project --python "$VENV/bin/python")

mkdir -p "$ROOT/evidence"

# Record the exact public benchmark revision and toolchain used so the final
# evaluation can be reproduced from a clean environment.
git -C "$VENDOR" rev-parse HEAD > "$ROOT/evidence/jaffle_shop_commit.txt"
{
  printf 'uv: '; uv --version
  printf 'Python selector: %s\n' "$PYTHON_VERSION"
  printf 'Python actual: '; "${UV_RUN[@]}" python --version
  "${UV_RUN[@]}" dbt --version
  printf 'Jaffle Shop commit: '; cat "$ROOT/evidence/jaffle_shop_commit.txt"
} | tee "$ROOT/evidence/environment.txt"

cat <<MSG

Bootstrap complete.
Environment: $VENV
Requested Python selector: $PYTHON_VERSION
Recorded environment: $ROOT/evidence/environment.txt
Next: ./scripts/capture_golden.sh
MSG
