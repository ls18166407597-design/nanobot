<div align="center">
  <p align="right">
    <a href="README_EN.md">English</a> | <strong>简体中文</strong>
  </p>
  <h1>nanobot: 极轻量级桌面 AI 秘书 (进阶增加版) </h1>
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

 **nanobot (Secretary Edition)** 是一款具备**高度自主权**和**执行契约**的个人 AI 秘书。它延续了原始项目极简的代码风骨，但在逻辑深度、感知能力和开发者体验 (DX) 上进行了全方位增强。

## ⚖️ 版本对比 (VS Original)

| 特性 | 原始 Nanobot | **秘书进阶版 (Secretary Edition)** |
| :--- | :--- | :--- |
| **核心角色** | 通用 AI 助手 | **主动秘书 ( 经理-员工执行模型)** |
| **行动契约** | 无特定协议 | **透明委派、失败请示、结果验证** |
| **OS 掌控** | 仅限 Shell 命令行 | **macOS 视觉 (OCR)、系统应用深度管理** |
| **桌面自动化** | 无 | **集成 Peekaboo，具备鼠标键盘控制权** |
| **感知能力** | 纯文本 | **原生 macOS 视觉框架，秒级识别屏幕内容** |
| **开发体验** | 基本启动指令 | **内置 Config/Doctor/New 调试套件** |

## 🌟 核心行为协议 (Behavioral Protocols)

我们为 Nanobot 注入了严谨的“秘书执行逻辑”：
- **单代理优先 (Single-Agent First)**: 默认由主代理闭环处理任务，只有在必要时才启用子任务（如长时任务或并行研究）。
- **透明委派 (Transparency)**: 当确实需要委派子任务时，必须明确告知“谁在做”及“为什么做”。
- **失败请示 (Ask on Failure)**: 严禁在工具失效时盲目尝试。Nanobot 会主动停下来向老板请示方向。
- **全中文交互**: 所有的提示词、说明文档及 Agent 话术均实现 100% 汉化。
- **智能化自愈 (Self-Healing)**: 
    - **引导式报错**: 工具失效时自动提供修正建议（如提示路径核查）。
    - **重复失败拦截**: 强制拦截完全相同的失败指令，彻底终止无效死循环。
    - **通用参数防御 (Type-Safety)**: 集中式类型转换层，自动修正 LLM 常见的 JSON 类型偏差。

## 🛠️ 开发者体验 (DX) 套件

不再需要手动编辑 JSON 或猜测环境问题：
- `nanobot config`: CLI 级配置管理（查看、修改、校验）。
- `nanobot doctor`: 系统健康诊断，一键排查环境冲突、API 连通性。
- `nanobot logs`: 实时追踪 `gateway.log` 和 `audit.log`（默认位于 `NANOBOT_HOME`），并显示实际路径，调试无忧。
- `nanobot new`: 快速脚手架（如 `nanobot new skill`）助力新能力开发。

## 🧰 任务与调度 (Task + Cron)
- **任务库**: `task(action="create", name="日报", description="生成日报", command="python scripts/daily.py")`
- **定时执行**: `cron(action="add", task_name="日报", cron_expr="0 9 * * *", tz="Asia/Shanghai")`
- **任务执行参数**: `task(action="run", name="日报", working_dir=".", timeout=60, confirm=true)`

## 🧩 本地 Gemini 桥接 (Local Bridge)

Nanobot 默认通过本地 `8045/8046` 端口访问 Gemini 模型（由外部桥接程序或本地应用提供）。

配置 nanobot 使用本地端口：
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
2.  **全链路 Failover (Provider Routing)**:
    - 主回合与系统回合统一接入注册表模型与故障切换策略。即使首选模型失效，也会自动降级到兼容候选。
3.  **动态别名映射**:
    - 支持在 `config.json` 中配置模型别名。例如你可以定义绰号 `qwen-3-8b`，系统会自动将其映射到物理模型 ID `Qwen/Qwen3-8B` 并正确处理对应的授权。
## 🛡️ 第六阶段：进阶网关稳定性与平台感 (Advanced Gateway & Platform Awareness)

最新的更新聚焦于网关的长期运行稳定性及其对 macOS 环境的深度感知：

1.  **单例运行保护 (Instance Locking)**:
    - 引入了基于 PID 文件的全局锁机制。现在系统会严格确保同一时间内只有一个 Nanobot 网关在运行，彻底解决了多进程冲突导致的 Token 浪费和状态错乱。
2.  **增强型应用识别 (AppKit Native)**:
    - 废弃了不可靠的 AppleScript 探测，全面接入 macOS 原生 `AppKit` 框架。
    - **Web App 深度识别**: 现在能精准分辨 Safari 和 Chrome 的 "Web App"（PWA），并反馈真实的 Web App ID，帮助 AI 更准确地匹配 Vision 自动化脚本。
3.  **实时状态反馈 (Zero-Latency Feedback)**:
    - 重构了启动入口为 `scripts/run_gateway.sh`，统一 `NANOBOT_HOME`、虚拟环境与日志路径，降低运行歧义。
    - 优化了审计日志 (`audit.log`) 的落盘逻辑，确保工具执行记录实时可见，调试更高效。

## 🖥️ 桌面自动化革命 (Desktop Automation)

Nanobot 现已突破 API 限制，具备**真实的桌面应用控制权**：
- **智能分发 (Smart Dispatch)**: 自动判断联系人所在的平台 (WeChat / Telegram) 并精准路由消息。
- **纯键盘流 (Pure Keyboard Flow)**: 甚至不需要鼠标坐标，利用系统级快捷键 (`Cmd+F/K` -> `Paste` -> `Enter`) 实现 100% 稳定的消息发送，彻底解决输入法干扰。
- **动态通讯录**: 支持通过自然语言 (`Add contact...`) 实时管理联系人映射，无需修改代码。
- **联网大脑 (Connected Brain)**: 集成 `Tavily` 深度搜索与 `TianAPI` 国内热点，实时掌握瞬息万变的信息。
- **金融引擎 (Finance Engine)**: 接入 `Tushare` 专业金融数据与飞书自动化报表，实现从数据抓取到办公自动化的闭环。

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

推荐本地一键启动（统一虚拟环境与日志路径）：
```bash
cd /Users/liusong/Downloads/nanobot && ./scripts/run_gateway.sh
```
提示：网关会自行写入 `NANOBOT_HOME/gateway.log`，如需实时查看请用 `nanobot logs -f`。

Telegram 常用会话命令：
- `/history` 查看最近会话
- `/use <session_key>` 切换会话
- `/new` 新建会话
- `/clear` 清空当前会话
- `/undo` 回退上一轮对话

核心链路回归（5 场景）：
```bash
cd /Users/liusong/Downloads/nanobot
.venv/bin/python scripts/smoke_regression.py --report .home/smoke_report.json
```

## 📁 极简架构 (Separated Architecture)

为了实现“内核稳定、大脑飞跃”，我们将项目重构为三位一体的物理隔离架构：

```
nanobot/
├── nanobot/         # ⚙️ [内核] 不可变引擎源码
├── workspace/       # 🧠 [大脑] 你的个性化 Prompt、Skill、脚本与记忆（技能单一来源）
├── .home/           # 📄 [运行] 临时日志与持久化配置存储
└── docs/            # 📖 [文档] 所有的指南与路线图 (汉化)
```

##  MODERNIZED WORKSPACE
```
workspace/
├── IDENTITY.md      # 核心使命与性格 (已合并 SOUL)
├── AGENTS.md        # 技术协议 (执行硬规则)
├── TOOLS.md         # 工具组合技 (多步流程 Recipes)
├── HEARTBEAT.md     # 主动维护区 (秘书日常任务)
├── scripts/         # [NEW] 自动化业务脚本 (微信/电报等)
└── tests/           # [NEW] 业务逻辑验证测试
```

## 🤝 项目文档

文档主入口与职责分工请先看：
- 🧭 **[文档导航（先看这个）](docs/文档导航.md)**

- ⚙️ **[配置指南](docs/配置指南.md)**
- 🗺️ **[路线图](docs/路线图.md)**
- 🏗️ **[项目结构](docs/项目结构.md)**

## 核心改造快照 (2026-02-11)

本轮聚焦“主干减重、边界清晰、可回归”：

- 回合执行引擎拆分：`AgentLoop` 中的执行状态机抽离为 `nanobot/agent/turn_engine.py`。
- 模型路由拆分：Provider failover 抽离为 `nanobot/agent/provider_router.py`。
- 工具装配拆分：默认工具注册抽离为 `nanobot/agent/tool_bootstrapper.py`。
- 会话服务抽分：会话切换与会话列表抽离为 `nanobot/session/service.py`。
- Telegram 通道拆分：格式化与媒体处理拆到 `nanobot/channels/telegram_format.py` 与 `nanobot/channels/telegram_media.py`。
- 契约文档与测试：新增 `ARCHITECTURE.md` 核心契约章节与 `nanobot/tests/test_contracts.py`。

---
<p align="center">
  <em> 感谢您使用 ✨ nanobot！您的私人高级行政秘书。</em>
</p>
