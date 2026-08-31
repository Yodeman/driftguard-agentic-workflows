#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 LABEL" >&2
  echo "Example: $0 iteration1" >&2
  exit 2
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="$1"
SRC="$ROOT/evidence/summary"
DST="$ROOT/evidence/milestones/$LABEL"
[[ -f "$SRC/aggregate.json" ]] || { echo "No summary found at $SRC. Run ./scripts/summarize_suite.sh first." >&2; exit 2; }
mkdir -p "$DST"
cp -a "$SRC/." "$DST/"
cat > "$DST/MILESTONE.txt" <<EOF
label=$LABEL
archived_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
echo "Archived summary milestone: $DST"
