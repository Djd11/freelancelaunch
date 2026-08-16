#!/usr/bin/env bash
# Stop any running instance of the web app and start it fresh on port 5000.
set -euo pipefail
cd "$(dirname "$0")"

# Kill any previous run.py or gunicorn server for this project.
pkill -f "run.py" 2>/dev/null || true
pkill -f "gunicorn.*wsgi" 2>/dev/null || true

PORT="${PORT:-5000}"

# Use the project venv — the system python3 lacks supabase/gunicorn.
PYTHON="${PYTHON:-.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
    echo "venv python not found at $PYTHON — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

echo "Starting app on port $PORT ..."
exec "$PYTHON" run.py
