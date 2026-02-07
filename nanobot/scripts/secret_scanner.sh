#!/bin/bash
# Project Sentinel: Secret Scanner
# Detects potential API keys and tokens before pushing to GitHub.

cd "$(dirname "$0")/../.." || exit 1

echo "🛡️ Project Sentinel: Running Secret Scan..."
echo "=========================================="

# Define patterns for sensitive tokens
PATTERNS=(
    "sk-[a-zA-Z0-9]{48}"          # OpenAI keys
    "ghp_[a-zA-Z0-9]{36}"          # GitHub PATs
    "xox[bpg]-[a-zA-Z0-9-]{10,}"   # Slack tokens
    "AIza[0-9A-Za-z_-]{35}"        # Google Cloud API Keys
    "sqp_[a-f0-9]{40}"             # SonarQube tokens
    "SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}" # SendGrid keys
)

FOUND=0

for pattern in "${PATTERNS[@]}"; do
    # Search while excluding known safe directories and config files
    MATCHES=$(grep -rE "$pattern" . \
        --exclude-dir={.venv,.git,__pycache__,openclaw,tests,docs,artifacts,brain} \
        --exclude={*.json,*.md,*.sh,pyproject.toml,.gitignore} \
        2>/dev/null)
    
    if [ -n "$MATCHES" ]; then
        echo "❌ [CRITICAL] Potential secret found with pattern: $pattern"
        echo "$MATCHES"
        FOUND=1
    fi
done

if [ $FOUND -eq 0 ]; then
    echo "✅ No obvious secrets found in the codebase."
    exit 0
else
    echo "⚠️  Audit FAILED: Please remove secrets before pushing."
    exit 1
fi
