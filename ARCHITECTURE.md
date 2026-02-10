# Nanobot 架构规范 (引擎与大脑隔离协议)

为了保持项目长期运行的整洁与可维护性，所有开发者及 AI 代理必须遵循以下物理架构分层规范。

## 1. 核心引擎 (Engine) - `nanobot/`
这是系统的底层基础设施，应保持“洁净”和“通用”。
- **`nanobot/agent/`**: 思考循环与上下文管理代码。
- **`nanobot/tools/`**: 核心工具定义（代码库）。
- **`nanobot/skills/`**: **仅限**系统核心技能（如 `summarize`, `cron`, `auth`）。
- **`nanobot/library/`**: 瘦身后的技能库（只读，供安装参考）。
- **`nanobot/maintenance/`**: 系统维护脚本。

## 2. 大脑工作区 (Brain/Workspace) - `workspace/`
这是 Nanobot 的“灵魂”所在地，包含所有用户定制化的逻辑。
- **`workspace/skills/`**: 你的所有业务技能副本和自定义技能。
- **`workspace/scripts/`**: 你编写的所有自动化脚本（如微信/电报控制）。
- **`workspace/memory/`**: 长期记忆存储。
- **`workspace/*.md`**: 身份（Identity）、性格（Soul）、执行协议（Agents）。

## 3. 运行时存储 (Store/Home) - `.home/`
由 `start.sh` 通过 `NANOBOT_HOME` 指定的临时数据区。
- **Logs**: `gateway.log`, `audit.log`。
- **Data**: `config.json`, `sessions/`, `tasks.json`。

## ❌ 严禁行为 (Anti-Patterns)
1. **禁止**在根目录放置业务脚本（请放入 `workspace/scripts/`）。
2. **禁止**修改 `nanobot/skills/` 下已被工作区覆盖的同名技能。
3. **禁止**在 `nanobot/` 核心代码库中硬编码个人配置。

---
*本规范于 2026-02-10 确立，旨在实现“内核稳定、大脑飞跃”的目标。*
