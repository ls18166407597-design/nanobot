<div align="center">
  <p align="right">
    <a href="README_EN.md">English</a> | <strong>简体中文</strong>
  </p>
  <img src="nanobot_logo.png" alt="nanobot" width="500">
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
- **全中文交互**: 所有的提示词、说明文档及 Agent 话术均实现 100% 汉化。

## 🛠️ 开发者体验 (DX) 套件

不再需要手动编辑 JSON 或猜测环境问题：
- `nanobot config`: CLI 级配置管理（查看、修改、校验）。
- `nanobot doctor`: 系统健康诊断，一键排查环境冲突。
- `nanobot new`: 快速脚手架（如 `nanobot new skill`）助力新能力开发。

## 🔥 高级核心优化

- ⚡ **并行工具执行**: 支持同时调用多个工具，复杂任务处理速度提升 50%。
- 🌍 **全球化代理支持**: 完美支持浏览器和消息渠道的代理配置，解决搜索超时问题。
- 🧠 **Light RAG 记忆与无限对话**: 检索式记忆加载，彻底解决 Context Window 爆炸问题。

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
- 🏗️ **[项目分层结构说明](docs/PROJECT_STRUCTURE.md)**

---
<p align="center">
  <em> 感谢您使用 ✨ nanobot！您的私人高级行政秘书。🐾</em>
</p>
