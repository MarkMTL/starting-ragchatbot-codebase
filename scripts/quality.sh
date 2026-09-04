#!/bin/bash
# CI-friendly quality gate: lint + format check. Makes no changes.
# Exits non-zero if any check fails. Run scripts/format.sh to fix.
set -e
cd "$(dirname "$0")/.."

echo "==> ruff check"
uv run ruff check backend/ main.py

echo "==> black --check"
uv run black --check backend/ main.py

echo "All quality checks passed."
