---
name: project-sentinel
description: Expert-level project auditing and safe GitHub synchronization. Handles linting, secret scanning, line-count monitoring, and bilingual documentation verification.
metadata:
  {
    "nanobot": {
      "emoji": "🛡️",
      "requires": { "bins": ["ruff", "git", "bash"] },
      "always": true
    }
  }
---

# Project Sentinel 🛡️

Maintain the "Premium" quality of Nanobot with automated audits and secure synchronization.

## 📋 Core Commands

### 1. Full Audit (`audit-all`)
Runs a comprehensive check including linting, formatting, secret scanning, and codebase stats.
```bash
bash nanobot/scripts/quality_audit.sh && bash nanobot/scripts/secret_scanner.sh
```

### 2. Safe Push (`safe-push`)
Performs a full audit and verifies bilingual sync before committing and pushing to GitHub.
```bash
bash nanobot/scripts/safe_push.sh "your commit message"
```

### 3. Secret Scan Only (`scan-secrets`)
Quickly check for exposed API keys or sensitive tokens.
```bash
bash nanobot/scripts/secret_scanner.sh
```

---

## 🛡️ Guiding Principles
- **Never Push Lint Errors**: Maintain a clean, professional codebase.
- **Sub-5k Core Lines**: Always monitor `bash core_agent_lines.sh` to keep the project lightweight.
- **Bilingual First**: Every major feature update must have both `README.md` and `README_EN.md` updated.
- **Zero Secrets**: Do not commit API keys. Use `config.json` for all credentials.

## 📊 Success Metrics
- **Ruff**: 0 errors, 0 warnings.
- **Format**: Consistent black-style formatting.
- **Line Count**: Keep core agent logic under 5,000 lines.
- **Sync**: Origin/main always matches the high-quality local state.
