#!/usr/bin/env bash
# Start everything for a demo: PostgreSQL, the API and the website.
#   scripts/start.sh          (Ctrl-C stops the API and the website; the database keeps running)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

"$ROOT/scripts/db.sh" status | grep -q "server is running" || "$ROOT/scripts/db.sh" start

cd "$ROOT/03-backend"
"$HOME/.yupreserved/venv/bin/uvicorn" app.main:app --port 8000 &
API=$!
trap 'kill $API 2>/dev/null' EXIT

cd "$ROOT/05-frontend"
[ -d node_modules ] || npm install --no-audit --no-fund
echo "→ website: http://localhost:5173    API docs: http://localhost:8000/docs"
npm run dev -- --port 5173
