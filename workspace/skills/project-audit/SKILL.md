---
name: project-audit
description: 代码质量、结构完整性以及与 GitHub 同步的综合审计工具。用于代码检查 (Ruff)、代码统计、密钥扫描和自动 GitHub 推送。
metadata:
  {
    "nanobot": {
      "emoji": "🛡️",
      "requires": { "bins": ["ruff", "git", "bash"] },
      "always": true
    }
  }
---

# 项目审计技能 (Project Audit Skill)

此技能提供了一个统一的工作流程，用于维护 Nanobot 项目的高质量标准。

## 🛠️ 动作 (Actions)

### 1. 代码检查 (Ruff)
深度检查 Python 代码库中的错误、风格问题和导入排序。
```bash
ruff check .
```

### 2. 结构统计
监控项目的“轻量级”状态。
```bash
bash core_agent_lines.sh
```

### 3. 密钥扫描 (安全第一)
在推送之前搜索意外暴露的 Token 或敏感数据模式。
```bash
grep -rE "sk-[a-zA-Z0-9]{48}|ghp_[a-zA-Z0-9]{36}" . --exclude-dir=.venv
```

### 4. 自动 GitHub 同步
一站式提交和推送更改。
```bash
git add . && git commit -m "feat/fix: [desc]" && git push origin main
```

---

## 📋 综合审计工作流

在发布或重大推送之前执行完整的“高级”检查：

1. **Lint**: `ruff check .` (首先修复任何错误)
2. **格式检查**: `ruff format --check .`
3. **统计审计**: `bash core_agent_lines.sh` 
4. **密钥扫描**: 运行上面的 grep 命令。
5. **同步**: 仅当上述所有检查通过时提交并推送。

## 💡 最佳实践
- **决不要推送带有 Lint 错误的代码**: 这会降低项目的声誉。
- **有意义的提交**: 使用约定式提交 (feat:, fix:, docs:, chore:)。
- **检查双语同步**: 确保 `README.md` 和 `README_EN.md` 的里程碑一致。
