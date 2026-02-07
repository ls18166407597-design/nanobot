# System Cleaner Skill 🧹

This skill enables Nanobot to proactively analyze and clean system junk, caches, and redundant development files.

## Commands

### 📊 `analyze-junk`
Runs a deep scan of common junk locations and reports specific, actionable findings.
```bash
# Scan Trash, Caches, and Logs
echo "--- Trash ---" && du -sh ~/.Trash
echo "--- User Caches ---" && du -sh ~/Library/Caches
echo "--- User Logs ---" && du -sh ~/Library/Logs

# Scan Development Junk
echo "--- venv/node_modules Scan ---"
find ~/Downloads -name "node_modules" -type d -prune -exec du -sh {} + 2>/dev/null
find ~/Downloads -name ".venv" -type d -prune -exec du -sh {} + 2>/dev/null
find ~/Downloads -name "venv" -type d -prune -exec du -sh {} + 2>/dev/null

# Scan Large Downloads
echo "--- Large Downloads (>100M) ---"
find ~/Downloads -type f -size +100M -exec ls -lh {} +
```

### 🧹 `clean-all-safe`
Cleans safe-to-remove caches and logs.
```bash
rm -rf ~/Library/Caches/*
rm -rf ~/Library/Logs/*
rm -rf ~/.Trash/*
brew cleanup
```

## Guiding Principles
1.  **Don't Summarize, Analyze**: Give the Boss specific paths and sizes.
2.  **Safety First**: Never delete user documents or unknown folders without confirmation.
3.  **Proactive Suggestion**: If you find a `.venv` that hasn't been touched in months, suggest its deletion.
