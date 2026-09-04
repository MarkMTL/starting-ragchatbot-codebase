#!/bin/bash
# Auto-format all Python code with black and fix import order with ruff.
set -e
cd "$(dirname "$0")/.."

echo "Sorting imports (ruff)..."
uv run ruff check --select I --fix backend/ main.py

echo "Formatting (black)..."
uv run black backend/ main.py

echo "Done."
