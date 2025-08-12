#!/bin/bash
# Quick smoke test for Tyler examples
# Run from workspace root: ./smoke-test-tyler.sh

echo "🧪 Running Tyler Examples Smoke Test..."
echo ""

# Suppress Python warnings
export PYTHONWARNINGS="ignore"

# Use uv to run the smoke test script with warning suppression
uv run python -W ignore packages/tyler/examples/smoke_test_examples.py "$@"
