#!/usr/bin/env bash
set -euo pipefail

PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Error: python3 not found. Install Python 3.10+ and retry." >&2
  exit 1
fi

echo "Creating virtual environment (venv)..."
$PY -m venv venv

echo "Activating venv and installing dependencies..."
# shellcheck disable=SC1091
. venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
  else
    echo "No .env.example found. Create a .env file as needed."
  fi
else
  echo ".env already exists — leaving in place"
fi

echo "Setup complete. Activate the virtualenv with:"
echo "  source venv/bin/activate"
echo "Run tests: python -m pytest tests/ -q"
