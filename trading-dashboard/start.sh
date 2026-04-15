#!/usr/bin/env bash
# ─── Trading Dashboard — one-shot startup ────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Backend ───────────────────────────────────────────────────────────────────
echo "==> Setting up Python backend…"
cd "$SCRIPT_DIR/backend"

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found"; exit 1
fi

# Create virtual environment if missing
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet -r requirements.txt

echo "==> Starting FastAPI backend on http://localhost:8000 …"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "    Backend PID: $BACKEND_PID"

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "==> Setting up React frontend…"
cd "$SCRIPT_DIR/frontend"

if ! command -v node &>/dev/null; then
  echo "ERROR: node not found — install Node.js >= 18"; exit 1
fi

if [ ! -d "node_modules" ]; then
  echo "==> Installing npm packages…"
  npm install
fi

echo "==> Starting Vite dev server on http://localhost:5173 …"
npm run dev &
FRONTEND_PID=$!
echo "    Frontend PID: $FRONTEND_PID"

echo ""
echo "  Dashboard: http://localhost:5173"
echo "  API docs:  http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Wait and clean up on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
