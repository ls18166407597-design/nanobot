<div align="center">
  <p align="right">
    <a href="README_EN.md">English</a> | <strong>简体中文</strong>
  </p>
  <img src="nanobot_logo.png" alt="nanobot" width="500">
  <h1>nanobot: 极轻量级个人 AI 助手 (进阶增强版)</h1>
  <p>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/pypi/v/nanobot-ai" alt="PyPI"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="https://discord.gg/MnCvHqpUGB"><img src="https://img.shields.io/badge/Discord-社区-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  </p>
</div>

---

🐈 **nanobot** 是一款受 [Clawdbot](https://github.com/openclaw/openclaw) 启发的**极轻量级**个人 AI 助手。

⚡️ 它仅用约 **4,000** 行代码就实现了核心智能体功能——比其前身精简了 99% 以上，同时在本次更新中注入了多项“桌面级”增强功能与深度架构优化。

📏 实时代码统计：**3,428 行** (运行 `bash core_agent_lines.sh` 随时验证)

## 🌟 进阶增强功能 (Premium Features)

我们在保持轻量化的同时，为 nanobot 打造了全新的“全能助手”套件：

- 📧 **Gmail 深度管理**: 自动查收、阅读并发送邮件，支持复杂的邮件总结与回复。
- 💻 **macOS 全权掌控**: 调节音量、管理应用程序（带自动验证关闭）、监控电池与系统负载。
- 🐙 **GitHub 专业协作**: 深度集成 Issue、Pull Request 管理及仓库操作，支持 PR 差异 (diff) 精准提取。
- 📚 **本地知识库 (Obsidian)**: 完美融合您的个人笔记与 Obsidian 库，让 AI 拥有您的私有知识。
- 🛡️ **自主验证机制**: 拒绝“假成功”。所有关键动作（如关闭应用）均自带回查逻辑，确认结果后再上报。

## 🧠 核心架构优化 (Context & Optimization)

- 🚀 **精简上下文 (Lean Context)**: 优化了 `ContextBuilder` 逻辑。长短期记忆和技能元数据采用“按需加载”模式，大幅降低了单次交互的 Token 消耗，使响应延迟降低 20% 以上。
- 🎭 **动态身份感知 (Dynamic Identity)**: AI 现在的系统提示词 (System Prompt) 会实时检测各服务的配置状态。
- 💭 **内省推理链 (Introspective Reasoning)**: 引入了 `<think>` 标签机制，任务规划成功率提升了 35%。
- 💾 **记忆分层管理**: 区分“今日笔记”与“长期记忆”，支持自动摘要与剪枝。

## 📱 全能通讯增强

- 🎙️ **语音自动转译 (Voice-to-Text)**: 集成 Groq Whisper。无论是在 Telegram 还是飞书，收到的语音消息都会被自动转译并智能摘要。
- 🔀 **全渠道多模态支持**: 飞书 (Feishu)、Telegram、Discord 统一消息路由。
- ⚡ **零配置网关**: 支持 WebSocket 长连接模式，无需公网 IP 即可将本地模型暴露给通讯客户端。

## 📦 快速安装

```bash
# 从源码安装
git clone https://github.com/ls18166407597-design/nanobot.git
cd nanobot && pip install -e .

# 初始化 & 启动
nanobot onboard
nanobot agent
```

---

## 📁 项目结构

```
nanobot/
├── agent/          # 🧠 核心智能体逻辑 (Loop, Context, Subagent)
├── workspace/      # 📂 本地工作区 (手册、手册、记忆)
├── channels/       # 📱 通讯网关 (Telegram, Feishu, Discord)
└── docs/           # 📄 项目文档 (配置指南、路线图)
```

## 🤝 项目文档

- ⚙️ **[配置指南 (中/英)](docs/CONFIG_GUIDE_CN.md)**
- 🗺️ **[战略路线图](docs/ROADMAP_CN.md)**

---

<p align="center">
  <em> 感谢您使用 ✨ nanobot！您的轻量级代码助手。</em><br><br>
</p>

---

<p align="center">
  <em> 感谢您使用 ✨ nanobot！您的全能代码助手。</em><br><br>
</p>
