#!/usr/bin/env bash
# The full local gate: what CONTRIBUTING.md asks you to run before pushing.
# CI is deliberately lighter (one Python, `ruff check`, deterministic core tests);
# the format check and the GUI/MCP/eval/e2e surfaces are validated here instead, so
# validation shifts left onto the developer's machine (coding standard Rule 18).
#
# Exits non-zero on the first failing step so a red gate is impossible to miss.
# Run from the repo root: `scripts/check.sh` (or `make check`).
set -euo pipefail

# Match CI's pinned ruff so a newer local release cannot disagree with the runner.
RUFF_PIN="0.15.21"
if ! ruff --version 2>/dev/null | grep -q "$RUFF_PIN"; then
  echo "note: CI pins ruff==$RUFF_PIN; your ruff is $(ruff --version 2>/dev/null || echo absent)." >&2
  echo "      install the pin with: pip install 'ruff==$RUFF_PIN'" >&2
fi

echo "==> ruff check (standpoint tests skills)"
ruff check standpoint tests skills

echo "==> ruff format --check (standpoint tests)"
ruff format --check standpoint tests

echo "==> pytest (core + any installed surface; each heavy surface self-skips)"
pytest tests/ -q

echo "==> gate green"
