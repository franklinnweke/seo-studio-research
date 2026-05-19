#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

BACKEND_PID=""
FRONTEND_PID=""

ensure_port_free() {
  local port="$1"
  local label="$2"

  if lsof -ti "tcp:${port}" >/dev/null 2>&1; then
    echo "${label} port ${port} is already in use."
    echo "Stop the existing process or set a different port before running this script."
    exit 1
  fi
}

python_bin() {
  if command -v python3.11 >/dev/null 2>&1; then
    echo "python3.11"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi

  echo "Python 3.11+ is required but was not found." >&2
  exit 1
}

cleanup() {
  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi

  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

ensure_port_free "$BACKEND_PORT" "Backend"
ensure_port_free "$FRONTEND_PORT" "Frontend"

PYTHON="$(python_bin)"

if [[ ! -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  echo "Creating backend virtual environment..."
  (cd "$BACKEND_DIR" && "$PYTHON" -m venv .venv)
fi

if [[ ! -f "$BACKEND_DIR/.venv/.requirements-installed" ]] ||
  [[ "$BACKEND_DIR/requirements.txt" -nt "$BACKEND_DIR/.venv/.requirements-installed" ]]; then
  echo "Installing backend dependencies..."
  (cd "$BACKEND_DIR" && .venv/bin/pip install -r requirements.txt)
  touch "$BACKEND_DIR/.venv/.requirements-installed"
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

echo "Starting backend:  http://${BACKEND_HOST}:${BACKEND_PORT}"
(cd "$BACKEND_DIR" && .venv/bin/uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT") &
BACKEND_PID="$!"

echo "Starting frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
(cd "$FRONTEND_DIR" && npm run dev -- --hostname "$FRONTEND_HOST" --port "$FRONTEND_PORT") &
FRONTEND_PID="$!"

echo
echo "seo-studio is starting."
echo "Press Ctrl+C to stop both servers."
echo

while true; do
  if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    wait "$BACKEND_PID"
    exit_code="$?"
    exit "$exit_code"
  fi

  if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    wait "$FRONTEND_PID"
    exit_code="$?"
    exit "$exit_code"
  fi

  sleep 1
done
