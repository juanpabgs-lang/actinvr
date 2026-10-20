#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ONB_VAR_DIR="${ONB_VAR_DIR:-$ROOT/backend/var}"
export ONB_SEED="${ONB_SEED:-1}"
export ONB_SUMMARY="${ONB_SUMMARY:-template}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

if ! curl -sf "http://127.0.0.1:11434/api/version" >/dev/null; then
  echo "Ollama no está en 127.0.0.1:11434. El alta funciona igual; los resúmenes usarán la plantilla."
fi

cd "$ROOT/backend"
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8013 --reload &
API=$!
trap 'kill $API' EXIT
cd "$ROOT/frontend"
if [[ "${1:-}" == "preview" ]]; then
  npm run demo
else
  npm run dev
fi
