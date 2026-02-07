---
name: project-audit
description: Comprehensive tool for auditing code quality, structural integrity, and synchronizing with GitHub. Use for linting (Ruff), code stats, secret scanning, and automated GitHub pushes.
metadata:
  {
    "nanobot": {
      "emoji": "🛡️",
      "requires": { "bins": ["ruff", "git", "bash"] },
      "always": true
    }
  }
---

# Project Audit Skill

This skill provides a unified workflow for maintaining the high-quality standards of the Nanobot project.

## 🛠️ Actions

### 1. Code Linting (Ruff)
Run a deep check of the Python codebase for errors, style issues, and import sorting.
```bash
ruff check .
```

### 2. Structural Stats
Monitor the "lightweight" status of the project.
```bash
bash core_agent_lines.sh
```

### 3. Secret Scanning (Safety First)
Search for accidentally exposed tokens or sensitive data pattern before pushing.
```bash
grep -rE "sk-[a-zA-Z0-9]{48}|ghp_[a-zA-Z0-9]{36}" . --exclude-dir=.venv
```

### 4. Automated GitHub Sync
A one-stop action to commit and push changes.
```bash
git add . && git commit -m "feat/fix: [desc]" && git push origin main
```

---

## 📋 Comprehensive Audit Workflow

To perform a full "Premium" check before release or major push:

1. **Lint**: `ruff check .` (Fix any errors first)
2. **Format Check**: `ruff format --check .`
3. **Stat Audit**: `bash core_agent_lines.sh` (Ensure we are under 5,000 core lines)
4. **Secret Scan**: Run the grep command above.
5. **Sync**: Commit and push only if all above pass.

## 💡 Best Practices
- **Never push with lint errors**: It lowers the project's reputation.
- **Meaningful Commits**: Use conventional commits (feat:, fix:, docs:, chore:).
- **Check Bilingual Sync**: Ensure `README.md` and `README_EN.md` milestones are identical.
