<div align="center">
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

⚡️ 它仅用约 **4,000** 行代码就实现了核心智能体功能——比其前身精简了 99% 以上，同时在本次更新中注入了多项“桌面级”增强功能。

📏 实时代码统计：**3,428 行** (运行 `bash core_agent_lines.sh` 随时验证)

## 🌟 进阶增强功能 (Premium Features)

我们在保持轻量化的同时，为 nanobot 打造了全新的“全能助手”套件：

- 📧 **Gmail 深度管理**: 自动查收、阅读并发送邮件，支持复杂的邮件总结。
- 💻 **macOS 全权掌控**: 调节音量、管理应用程序（带自动验证关闭）、监控电池与系统负载。
- 🐙 **GitHub 专业协作**: 深度集成 Issue、Pull Request 管理及仓库操作，成为您的代码二号机。
- 📚 **本地知识库 (Obsidian)**: 完美融合您的个人笔记与 Obsidian 库，让 AI 拥有您的私有知识。
- 🛡️ **自主验证机制**: 所有关键动作均自带“回查”逻辑，确保任务真实完成。

## ✨ 核心特性

<table align="center">
  <tr align="center">
    <th><p align="center">📧 全能邮件管家</p></th>
    <th><p align="center">💻 macOS 系统掌控</p></th>
    <th><p align="center">🐙 GitHub 深度协作</p></th>
    <th><p align="center">📚 个人知识助手</p></th>
  </tr>
  <tr>
    <td align="center">收发邮件 • 总结摘要</td>
    <td align="center">音量调节 • App 管理</td>
    <td align="center">Issue 管理 • PR 审查</td>
    <td align="center">笔记检索 • 知识连接</td>
  </tr>
</table>

## 📦 快速安装

**从源码安装** (推荐开发者使用)

```bash
git clone https://github.com/HKUDS/nanobot.git
cd nanobot
pip install -e .
```

## 🚀 快速开始

> [!TIP]
> 在 `~/.nanobot/config.json` 中设置您的 API 密钥。

**1. 初始化**
```bash
nanobot onboard
```

**2. 启动网关 (支持 Telegram/飞书/Discord)**
```bash
nanobot gateway
```

## 🤖 自主配置与自我意识

nanobot 现在具备强大的“环境感知”能力：
- **主动配置**: 您可以直接发送 `{ "email": "...", "password": "..." }` 给它，它会识别并自动完成工具设置。
- **状态感知**: 系统提示词会实时反馈哪些工具已就绪，拒绝冗余教学，直奔任务核心。

## ⚙️ 安全性

> [!IMPORTANT]
> nanobot 始终将您的数据隐私放在首位。所有配置文件均存储在本地 `~/.nanobot/` 目录下，不会上传至任何第三方服务器。

## 📁 项目结构

```
nanobot/
├── agent/          # 🧠 核心智能体逻辑
│   ├── loop.py     #    智能体循环 (LLM ↔ 工具执行)
│   ├── context.py  #    动态提示词构建
│   ├── tools/      #    全能工具箱 (Gmail, GitHub, Mac, etc.)
├── workspace/      # 📂 工作区 (AGENTS.md, TOOLS.md 手册)
├── channels/       # 📱 通讯通道 (Telegram, Feishu, Discord)
├── cron/           # ⏰ 任务调度
└── heartbeat/      # 💓 智能体主动唤醒
```

## 🤝 路线图 (Roadmap)

- [x] **邮件/系统/GitHub/知识库** — 深度桌面增强
- [x] **语音转文字** — 支持 Groq Whisper
- [ ] **多模态能力** — 支持图片与视频理解
- [ ] **动态工具发现** — 自动识别新增工具集
- [ ] **多模型自动回退** — 提高 API 服务的鲁棒性

---

<p align="center">
  <em> 感谢您使用 ✨ nanobot！您的全能代码助手。</em><br><br>
</p>
