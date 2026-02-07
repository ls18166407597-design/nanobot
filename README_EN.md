<div align="center">
  <p align="right">
    <strong>English</strong> | <a href="README.md">简体中文</a>
  </p>
  <img src="nanobot_logo.png" alt="nanobot" width="500">
  <h1>nanobot: Ultra-Lightweight Personal AI Assistant (Enhanced)</h1>
  <p>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/pypi/v/nanobot-ai" alt="PyPI"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="https://discord.gg/MnCvHqpUGB"><img src="https://img.shields.io/badge/Discord-Community-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  </p>
</div>

---

🐈 **nanobot** is an **ultra-lightweight** personal AI assistant inspired by [Clawdbot](https://github.com/openclaw/openclaw).

⚡️ It delivers core agent functionality in just ~4,000 lines of code — **99% smaller** than its predecessor, while injecting experimental desktop-grade features and deep architectural optimizations.

📏 Real-time code stats: **3,428 lines** (run `bash core_agent_lines.sh` to verify).

## 🌟 Premium Features

While staying lightweight, nanobot provides a powerful tool suite:

- 📧 **Gmail Management**: List, read, and send emails with intelligent summarization and drafting.
- 💻 **macOS Control**: Volume control, App management (with verified closure), and system stats.
- 🐙 **GitHub Collaboration**: Manage Issues and Pull Requests with precise diff extraction.
- 📚 **Learning Memory (Obsidian)**: Seamlessly integrates with your local Markdown vault/Obsidian workspace.
- 🛡️ **Autonomous Verification**: No "fake success". Critical actions are verified via process checks before reporting.

## 🧠 Core Optimizations (Context & Performance)

- 🚀 **Lean Context**: Optimized `ContextBuilder` for minimal token usage and 20%+ faster response times.
- 🎭 **Dynamic Awareness**: The system prompt automatically detects configured tools (Gmail, GitHub, etc.).
- 💭 **Introspective Reasoning**: Uses `<think>` tags for deep planning and increased task success rates.
- 💾 **Tiered Memory**: Separates "Daily Notes" from "Long-term Memory" with automatic pruning.

## 📱 Multi-Channel Excellence

- 🎙️ **Voice-to-Text**: Integrated Groq Whisper for automatic transcription in Telegram/Feishu.
- 🔀 **Universal Message Bus**: Unified routing for Telegram, Feishu, Discord, and more.
- ⚡ **Zero-Config Gateway**: WebSocket long-connection mode — no public IP required.

## 📦 Quick Start

> [!TIP]
> nanobot supports **Magic Onboarding**. Just send your credentials (API keys, etc.) directly to the AI to configure it.

```bash
# Install from source
git clone https://github.com/ls18166407597-design/nanobot.git
cd nanobot && pip install -e .

# Initialize & Start
nanobot onboard
nanobot agent
```

---

## 📁 Project Structure

```
nanobot/
├── agent/          # 🧠 Core Agent Logic (Loop, Context, Subagent)
├── workspace/      # 📂 Workspace (Manuals, Memory, Notes)
├── channels/       # 📱 Communication Channels (Telegram, Discord, etc.)
└── docs/           # 📄 Documentation (Config Guides, Roadmap)
```

## 🤝 Documentation

- ⚙️ **[Detailed Configuration Guide](docs/CONFIG_GUIDE.md)**
- 🗺️ **[Strategic Roadmap](docs/ROADMAP.md)**

---

<p align="center">
  <em> Thanks for using ✨ nanobot! Your lightweight coding companion. </em><br><br>
</p>
