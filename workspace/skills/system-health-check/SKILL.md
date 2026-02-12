---
name: system-health-check
description: Nanobot 的综合诊断和回归套件。更新后使用此技能验证核心系统（工具、感知、连接）。此技能针对 AI 助手进行了优化，以执行自我审计和立即修复错误。
---

# 系统健康检查 (AI 审计版)

此技能为 **AI 助手** 提供了一种系统化的方法，用于在修改代码后验证 Nanobot 的健康状况。

## 助手工作流 (Assistant Workflow)

当你 (AI 助手) 完成一项任务或修改了核心逻辑时:
1. **运行回归套件**: 执行带有 JSON 输出的诊断脚本。
2. **分析失败**: 如果任何测试失败，使用提供的错误信息来确定根本原因。
3. **修复并重新运行**: 应用必要的修复并再次运行审计，直到所有测试通过。
4. **向用户报告**: 只有在系统验证健康后，或者发现无法解决的阻塞问题时，才向用户报告。

## 待验证工具 (Tools to Verify)

- **文件系统**: `nanobot/agent/tools/filesystem.py`
- **Shell**: `nanobot/agent/tools/shell.py`
- **视觉 (Vision)**: `nanobot/agent/tools/mac_vision.py` (需要 `pyobjc`)
- **网关 (Gateway)**: `nanobot/cli/commands.py`

## 执行 (Execution)

运行回归套件:
```bash
python3 workspace/skills/system-health-check/scripts/regression_suite.py
```

检查生成的 `audit_report.json`，或者分析标准输出 (STDOUT)。
