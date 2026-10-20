#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/sbom"
mkdir -p "$OUT"
"$ROOT/backend/.venv/bin/pip" freeze > "$OUT/python.txt"
(cd "$ROOT/frontend" && npm ls --all --omit=dev > "$OUT/npm-prod.txt")
echo "SBOM escrito en $OUT. Superficie deliberadamente pequeña: sin kit de UI, sin CDN."
