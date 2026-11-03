#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " Running bakim-bloklari quality and validation checks"
echo "=========================================================="

# Locate project root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Resolve python interpreter
PYTHON=""
if [ -f "$REPO_ROOT/.venv/Scripts/python.exe" ]; then
    PYTHON="$REPO_ROOT/.venv/Scripts/python.exe"
elif [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
elif command -v python &>/dev/null; then
    PYTHON="python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v py &>/dev/null; then
    PYTHON="py -3"
else
    echo "Error: Python interpreter not found." >&2
    exit 1
fi

echo "Using Python: $PYTHON"
"$PYTHON" --version

echo ""
echo "[1/6] Running Ruff linter..."
"$PYTHON" -m ruff check src tests

echo ""
echo "[2/6] Running Ruff code format check..."
"$PYTHON" -m ruff format --check src tests

echo ""
echo "[3/6] Running Mypy static type checker..."
"$PYTHON" -m mypy src tests

echo ""
echo "[4/6] Running Pytest unit test suite & coverage (threshold >= 85%)..."
"$PYTHON" -m pytest --cov=bakim_bloklari --cov-report=term-missing --cov-fail-under=85

echo ""
echo "[5/6] Validating Home Assistant blueprint schemas & safety rules..."
"$PYTHON" -m bakim_bloklari.cli validate

echo ""
echo "[6/6] Executing 12 acceptance test scenarios in state simulator..."
"$PYTHON" -m bakim_bloklari.cli simulate

echo ""
echo "=========================================================="
echo " ALL CHECKS PASSED: Project is ready and verified (exit 0)"
echo "=========================================================="
exit 0
