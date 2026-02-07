#!/bin/bash
# Project Sentinel: Quality Audit
# Runs linting, formatting checks, and codebase line count verification.

cd "$(dirname "$0")/../.." || exit 1

echo "🔍 Project Sentinel: Running Quality Audit..."
echo "=========================================="

# 1. Check if ruff is installed
if ! command -v ruff &> /dev/null; then
    echo "❌ Error: 'ruff' is not installed. Please run 'pip install ruff'."
    exit 1
fi

# 2. Run Ruff Check
echo "Step 1: Running codebase linting (Ruff)..."
ruff check .
LINT_EXIT=$?

if [ $LINT_EXIT -ne 0 ]; then
    echo "❌ Linting FAILED. Please fix the errors above."
    exit 1
fi
echo "✅ Linting passed."

# 3. Run Ruff Format Check
echo "Step 2: Checking code formatting..."
ruff format --check .
FORMAT_EXIT=$?

if [ $FORMAT_EXIT -ne 0 ]; then
    echo "❌ Formatting check FAILED. Run 'ruff format .' to fix."
    exit 1
fi
echo "✅ Formatting check passed."

# 4. Core Line Count Monitor
echo "Step 3: Verifying codebase lightweight status..."
if [ -f "core_agent_lines.sh" ]; then
    bash core_agent_lines.sh
    TOTAL_LINES=$(bash core_agent_lines.sh | grep "Core total:" | awk '{print $3}')
    
    if [ "$TOTAL_LINES" -gt 5000 ]; then
        echo "⚠️  Warning: Project size exceeds 5,000 core lines ($TOTAL_LINES). Consider refactoring."
    else
        echo "✅ Lightweight status confirmed ($TOTAL_LINES lines)."
    fi
else
    echo "⚠️  Warning: core_agent_lines.sh not found. Skipping line count monitor."
fi

echo "=========================================="
echo "✨ Quality Audit COMPLETE."
exit 0
