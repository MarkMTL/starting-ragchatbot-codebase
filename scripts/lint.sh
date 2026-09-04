#!/bin/bash
# Lint Python code with ruff. No changes made; reports issues only.
set -e
cd "$(dirname "$0")/.."

uv run ruff check backend/ main.py
