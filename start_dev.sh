#!/usr/bin/env bash
set -e

# start_dev.sh - Start both backend and frontend for local development
# Usage: ./start_dev.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  echo ""
  echo "Shutting down..."
  # Kill background processes
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "$FRONTEND_PID" ]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

echo "=========================================="
echo " Starting development servers"
echo "=========================================="

# Start the backend (Flask on port 5021)
echo "[backend]  Starting Flask server on http://localhost:5021 ..."
cd "$SCRIPT_DIR/backend"
.venv/bin/python run.py &
BACKEND_PID=$!

# Start the frontend (Vite on port 3000)
echo "[frontend] Starting Vite dev server on http://localhost:3000 ..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo " Backend:  http://localhost:5021"
echo " Frontend: http://localhost:3000"
echo " Press Ctrl+C to stop both servers"
echo "=========================================="

# Wait for either process to exit
wait
