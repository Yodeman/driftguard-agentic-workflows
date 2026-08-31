#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor/jaffle_shop_duckdb"
VENV="$ROOT/.venv"
PYTHON_VERSION="${DRIFTGUARD_PYTHON:-3.13}"
JAFFLE_SHOP_COMMIT="${DRIFTGUARD_JAFFLE_COMMIT:-36bde6cba69d962b83be1d52fc65a0dce1cb4ebb}"

command -v uv >/dev/null 2>&1 || {
  echo "uv is required but was not found on PATH." >&2
  echo "Install uv first, then re-run ./scripts/bootstrap.sh" >&2
  exit 2
}

mkdir -p "$ROOT/vendor" "$ROOT/evidence"

if [[ ! -d "$VENDOR/.git" ]]; then
  rm -rf "$VENDOR"
  git clone --filter=blob:none --no-checkout https://github.com/dbt-labs/jaffle_shop_duckdb.git "$VENDOR"
fi

# Pin the public benchmark project to the exact revision used for the frozen
# experiment. Fetch the commit explicitly so reproduction does not depend on
# whatever happens to be latest on the duckdb branch.
git -C "$VENDOR" fetch --depth 1 origin "$JAFFLE_SHOP_COMMIT"
git -C "$VENDOR" checkout --detach "$JAFFLE_SHOP_COMMIT"

# Recreate the benchmark environment on every bootstrap. This prevents an
# older .venv (for example Python 3.12) from being silently reused when the
# benchmark selector is Python 3.13.
rm -rf "$VENV"
uv venv --python "$PYTHON_VERSION" "$VENV"

# Install the benchmark dependencies with uv rather than pip.
uv pip install --python "$VENV/bin/python" -r "$VENDOR/requirements.txt"

UV_RUN=(uv run --no-project --python "$VENV/bin/python")

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
