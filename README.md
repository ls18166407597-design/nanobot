<div align="center">
  <p align="right">
    <a href="README_EN.md">English</a> | <strong>简体中文</strong>
  </p>
  <h1>nanobot: 极轻量级桌面 AI 秘书 (进阶增加版) 🐈</h1>
  <p>
    <strong>由 [HKUDS/nanobot] 深度进化而来的操作系统级助手</strong>
  </p>
  <p>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/pypi/v/nanobot-ai" alt="PyPI"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

---

🐈 **nanobot (Secretary Edition)** 是一款具备**高度自主权**和**执行契约**的个人 AI 秘书。它延续了原始项目极简的代码风骨，但在逻辑深度、感知能力和开发者体验 (DX) 上进行了全方位增强。

## ⚖️ 版本对比 (VS Original)

| 特性 | 原始 Nanobot | **秘书进阶版 (Secretary Edition)** |
| :--- | :--- | :--- |
| **核心角色** | 通用 AI 助手 | **主动秘书 (🐈 经理-员工执行模型)** |
| **行动契约** | 无特定协议 | **透明委派、失败请示、结果验证** |
| **OS 掌控** | 仅限 Shell 命令行 | **macOS 视觉 (OCR)、系统应用深度管理** |
| **桌面自动化** | 无 | **集成 Peekaboo，具备鼠标键盘控制权** |
| **感知能力** | 纯文本 | **原生 macOS 视觉框架，秒级识别屏幕内容** |
| **开发体验** | 基本启动指令 | **内置 Config/Doctor/New 调试套件** |

## 🌟 核心行为协议 (Behavioral Protocols)

我们为 Nanobot 注入了严谨的“秘书执行逻辑”：
- **透明委派 (Transparency)**: 在将任务分配给子智能体时，Nanobot 必须明确告知“谁在做”及“为什么做”。
- **失败请示 (Ask on Failure)**: 严禁在工具失效时盲目尝试。Nanobot 会主动停下来向老板请示方向。
- **强制验证 (Mandatory Verification)**: 每一个修改操作后都必须通过读取工具验证结果，不接受“猜测的成功”。
- **架构硬化 (Hardened V2.0)**: 
    - **内容哈希熔断**: 拦截生成新 ID 的死循环调用。
    - **上下文去重**: 摘要自动扁平化，杜绝 Prompt 膨胀。
    - **路径深层审计**: 封堵 Shell 指令中的越界风险。
- **全中文交互**: 所有的提示词、说明文档及 Agent 话术均实现 100% 汉化。

## 🛠️ 开发者体验 (DX) 套件

不再需要手动编辑 JSON 或猜测环境问题：
- `nanobot config`: CLI 级配置管理（查看、修改、校验）。
- `nanobot doctor`: 系统健康诊断，一键排查环境冲突、API 连通性。
- `nanobot logs`: 实时追踪 `gateway.log` 和 `audit.log`（默认位于 `NANOBOT_HOME`），并显示实际路径，调试无忧。
- `nanobot new`: 快速脚手架（如 `nanobot new skill`）助力新能力开发。

## 🧰 任务与调度 (Task + Cron)
- **任务库**: `task(action="create", name="日报", description="生成日报", command="python scripts/daily.py")`
- **定时执行**: `cron(action="add", task_name="日报", cron_expr="0 9 * * *")`
- **任务执行参数**: `task(action="run", name="日报", working_dir=".", timeout=60, confirm=true)`
- **后台子任务管理**: `spawn(action="list")` / `spawn(action="status", task_id="...")` / `spawn(action="cancel", task_id="...")`

## 🧩 Antigravity OAuth + 本地桥接（OpenAI-Compatible）

如果你希望通过 Google OAuth 登录 Antigravity，但仍使用 OpenAI 兼容接口调用（最省事），可用本地桥接：

```bash
# 1) OAuth 登录（生成 antigravity_auth.json）
python3 scripts/antigravity_oauth_login.py --set-default-model

# 2) 启动桥接服务
python3 scripts/antigravity_bridge.py --port 8046
```

配置 nanobot 使用桥接：
```json
{
  "providers": {
    "openai": {
      "api_base": "http://127.0.0.1:8046/v1",
      "api_key": "dummy"
    }
  },
  "agents": {
    "defaults": {
      "model": "gemini-3-flash"
    }
  }
}
```

说明：
- `api_key` 只是占位，桥接会忽略它。
- 当前桥接仅支持非流式（`stream=false`）。

## 🔥 高级核心优化

- ⚡ **并行工具执行**: 支持同时调用多个工具，复杂任务处理速度提升 50%。
- 🌍 **全球化代理支持**: 完美支持浏览器和消息渠道的代理配置，解决搜索超时问题。
- 🧠 **Light RAG 记忆与无限对话**: 检索式记忆加载，彻底解决 Context Window 爆炸问题。

## 🛡️ 第四阶段：企业级可靠性 (Enterprise Reliability)

参考 OpenClaw 架构，我们引入了三道安全防线：

1.  **高级消息泳道 (Lanes)**:
    - 确保用户交互 (MAIN Lane) 永远优先于后台任务 (BACKGROUND Lane)，拒绝卡顿。
2.  **上下文智能卫士 (Context Guard)**:
    - 实时监控 Token 用量 (支持 GPT-4o/Claude 3)，在达到阈值 (85%) 时自动无损压缩，杜绝 "Context Exceeded" 崩溃。
3.  **多鉴权轮询 (Auth Rotation)**:
    - 遇到 API 429/5xx 错误时，自动将故障 Key 列入 "冷却名单" 并无缝切换备用线路，保障服务 100% 在线。

## 🛡️ 第五阶段：高可用路由与多模型治理 (High Availability & Governance)

在最新的更新中，我们进一步强化了 Nanobot 在复杂多模型环境下的生存能力：

1.  **精准模型路由 (Strict Provider Mapping)**:
    - 彻底重构了凭据匹配算法。现在系统会根据模型名称强制锁定供应商（例如 `gemini` 始终绑定本地代理，`qwen` 始终直连 SiliconFlow），杜绝了 API Key 与 Base URL 错配导致的“弗兰肯斯坦”型 401 报错。
2.  **全链路 Failover (Subagent Routing)**:
    - 子任务（Spawned Subagents）现在也接入了主脑的“注册表模型”。即使主线模型（如 GPT-4o）由于配额耗尽失效，子任务也会自动降级到兼容的备用模型执行。
3.  **动态别名映射**:
    - 支持在 `config.json` 中配置模型别名。例如你可以定义绰号 `qwen-3-8b`，系统会自动将其映射到物理模型 ID `Qwen/Qwen3-8B` 并正确处理对应的授权。
## 🖥️ 桌面自动化革命 (Desktop Automation)

Nanobot 现已突破 API 限制，具备**真实的桌面应用控制权**：
- **智能分发 (Smart Dispatch)**: 自动判断联系人所在的平台 (WeChat / Telegram) 并精准路由消息。
- **纯键盘流 (Pure Keyboard Flow)**: 甚至不需要鼠标坐标，利用系统级快捷键 (`Cmd+F/K` -> `Paste` -> `Enter`) 实现 100% 稳定的消息发送，彻底解决输入法干扰。
- **动态通讯录**: 支持通过自然语言 (`Add contact...`) 实时管理联系人映射，无需修改代码。
> 注：涉及网页搜索/浏览的 `browser` 操作需通过 `spawn` 子智能体执行。

## 📦 快速安装

```bash
# 从源码安装
git clone https://github.com/ls18166407597-design/nanobot.git
cd nanobot && pip install -e .

# 快速配置 & 启动
nanobot config check
nanobot doctor
nanobot gateway  # 启动完整网关 (支持 Telegram/飞书)
```

## 📁 现代化工作区架构

```
workspace/
├── IDENTITY.md      # 核心使命 (你是谁)
├── SOUL.md          # 灵魂与性格 (语气、价值观)
├── AGENTS.md        # 技术协议 (执行硬规则)
├── TOOLS.md         # 工具组合技 (多步流程 Recipes)
├── HEARTBEAT.md     # 主动维护区 (秘书日常任务)
└── memory/          # 动态增长的长短期记忆
```

## 🤝 项目文档

- ⚙️ **[高级配置指南](docs/CONFIG_GUIDE_CN.md)**
- 🗺️ **[版本演进路线图](docs/ROADMAP_CN.md)**
- 🧪 **全项目测试 SOP** (待补充)
- 🏗️ **[项目分层结构说明](docs/PROJECT_STRUCTURE.md)**

---
<p align="center">
  <em> 感谢您使用 ✨ nanobot！您的私人高级行政秘书。🐾</em>
</p>
