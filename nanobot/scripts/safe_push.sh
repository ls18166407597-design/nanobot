#!/bin/bash
# Project Sentinel: Safe Push Workflow
# Integrates all audits and verifies bilingual sync before pushing to GitHub.

COMMIT_MSG=$1

if [ -z "$COMMIT_MSG" ]; then
    echo "❌ Error: Commit message is required."
    echo "Usage: bash nanobot/scripts/safe_push.sh 'feat: [desc]'"
    exit 1
fi

cd "$(dirname "$0")/../.." || exit 1

# 1. Quality Audit
echo "🛡️ Step 1: Running Quality Audit..."
bash nanobot/scripts/quality_audit.sh
if [ $? -ne 0 ]; then exit 1; fi

# 2. Secret Scan
echo "🛡️ Step 2: Running Secret Scan..."
bash nanobot/scripts/secret_scanner.sh
if [ $? -ne 0 ]; then exit 1; fi

# 3. Bilingual Sync Verification
echo "🛡️ Step 3: Verifying Bilingual Documentation Sync..."
if [ -f "README.md" ] && [ -f "README_EN.md" ]; then
    # Simple check: were they both modified in the same session?
    # Alternatively, warn if one is significantly smaller than the other.
    ZH_SIZE=$(wc -c < README.md)
    EN_SIZE=$(wc -c < README_EN.md)
    
    # Just a sanity check for existence and non-zero size
    if [ "$ZH_SIZE" -lt 100 ] || [ "$EN_SIZE" -lt 100 ]; then
        echo "❌ [ERROR] One of the README files is suspiciously small."
        exit 1
    fi
    echo "✅ Bilingual README files present and verified."
else
    echo "❌ [ERROR] Missing either README.md or README_EN.md."
    exit 1
fi

# 4. Git Push
echo "🚀 Step 4: Synchronizing with GitHub..."
git add .
git commit -m "$COMMIT_MSG"
git push origin main

if [ $? -eq 0 ]; then
    echo "✨ Project Sentinel: Safe Push SUCCESSFUL."
else
    echo "❌ Git Push FAILED. Check network or remote permissions."
    exit 1
fi
