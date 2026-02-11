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

## 4. 核心契约 (Core Contracts)
以下契约属于“主干协议”，改动必须配套测试与迁移说明。

### 4.1 InboundMessage 会话契约
- 结构：`nanobot/bus/events.py::InboundMessage`
- 规则：
- 默认会话键 = `f"{channel}:{chat_id}"`。
- 若设置 `session_key_override`，则 `session_key` 必须优先返回 override。
- 不再依赖 `metadata["session_key"]` 作为正式协议（仅可用于历史兼容读取，不可作为新实现输入）。

### 4.2 ToolResult 协议
- 结构：`nanobot/agent/tools/base.py::ToolResult`
- 最小字段：
- `success: bool`
- `output: str`
- 可选控制字段：
- `remedy`
- `severity`
- `should_retry`
- `requires_user_confirmation`
- 规则：
- Tool 执行链路统一返回 `ToolResult`（兼容层可临时兜底，但不应作为新代码依赖）。

### 4.3 TurnEngine 执行契约
- 结构：`nanobot/agent/turn_engine.py::TurnEngine.run`
- 输入：
- `messages`
- `trace_id`
- `parse_calls_from_text`
- `include_severity`
- `parallel_tool_exec`
- `compact_after_tools`
- 输出：
- `str | None`（最终可见回复，或空）
- 规则：
- 负责单轮执行状态机（LLM -> tools -> compact -> finalize）。
- 死循环检测、自愈注入、工具结果格式化在此层统一处理。

### 4.4 ProviderRouter 路由契约
- 结构：`nanobot/agent/provider_router.py::ProviderRouter.chat_with_failover`
- 输入：
- `messages`
- `tools`
- 输出：
- `LLMResponse`
- 规则：
- 必须保证“所有候选失败时”返回可解释的 `LLMResponse(finish_reason="error")`。
- 冷却策略与候选轮转由该层维护，`AgentLoop` 不重复实现。

### 4.5 AgentLoop 边界契约
- 结构：`nanobot/agent/loop.py::AgentLoop`
- 规则：
- 职责限定为：消息路由、生命周期、上下文构建、调用 TurnEngine、结果发布。
- 不直接承载 provider failover 与回合执行细节。

## 5. 变更门禁 (Change Gate)
涉及核心契约改动时，必须同时满足：
1. 更新本文件 `Core Contracts` 对应条目。
2. 增补或更新 `nanobot/tests/test_contracts.py`。
3. 全量 `pytest` 通过后方可合并。

---
*本规范于 2026-02-10 确立，旨在实现“内核稳定、大脑飞跃”的目标。*
