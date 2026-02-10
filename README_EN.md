<div align="center">
  <p align="right">
    <strong>English</strong> | <a href="README.md">简体中文</a>
  </p>
  <img src="nanobot_logo.png" alt="nanobot" width="500">
  <h1>nanobot: Ultra-Lightweight OS Secretary (Advanced Edition) </h1>
  <p>
    <strong>Autonomous assistant evolved from [HKUDS/nanobot] with OS-level capabilities</strong>
  </p>
  <p>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/pypi/v/nanobot-ai" alt="PyPI"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

---

 **nanobot (Secretary Edition)** is a deeply autonomous personal AI assistant with a strict **Execution Contract**. It maintains the minimalist spirit of the original project while significantly enhancing logic depth, perception, and Developer Experience (DX).

## ⚖️ Comparison (VS Original)

| Feature | Original Nanobot | **Secretary Edition** |
| :--- | :--- | :--- |
| **Core Role** | General AI Assistant | **Proactive Secretary ( Manager-Employee model)** |
| **Execution Protocol**| None | **Transparent Delegation, Ask-on-Failure, Result Verification** |
| **OS Control** | Shell only | **macOS Vision (OCR), Apps, Audio, System Monitoring** |
| **Desktop Automation** | None | **Full Mouse/Keyboard control via Peekaboo** |
| **Perception** | Text only | **Native macOS Vision framework for screen reading** |
| **Dev Experience** | Basic scripts | **Integrated Config/Doctor/New Suite** |

## 🌟 Behavioral Protocols

We’ve injected Nanobot with professional secretary logic:
- **Transparent Delegation**: When assigning tasks to sub-agents, Nanobot clearly states "Who" and "Why".
- **Ask on Failure**: No blind trial-and-error. Nanobot pauses and asks the Boss for direction if a tool fails.
- **Mandatory Verification**: Every "Write" or "Execute" action is followed by a "Read" to confirm the actual outcome.
- **100% Localization**: All internal prompts and user-facing manuals are fully translated into Simplified Chinese.

## 🛠️ Developer Experience (DX) Suite

No more manual JSON hacking:
- `nanobot config`: CLI-level configuration management (View, Set, Check).
- `nanobot doctor`: System health diagnostics to resolve environment conflicts.
- `nanobot new`: Rapid scaffolding (e.g., `nanobot new skill`) for capability expansion.
- `nanobot logs`: Tail `gateway.log` and `audit.log` (defaults to `NANOBOT_HOME`) and prints the resolved path.

## 🧰 Task + Cron
- **Task library**: `task(action="create", name="daily", description="Generate daily report", command="python scripts/daily.py")`
- **Scheduled run**: `cron(action="add", task_name="daily", cron_expr="0 9 * * *")`
- **Run with options**: `task(action="run", name="daily", working_dir=".", timeout=60, confirm=true)`
- **Subagent management**: `spawn(action="list")` / `spawn(action="status", task_id="...")` / `spawn(action="cancel", task_id="...")`

## 🧩 Local Gemini Bridge

Nanobot accesses Gemini models via a local bridge on port `8045/8046` (provided by an external application or local bridge service).

Configure nanobot to use the local port:
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

Notes:
- `api_key` is a placeholder; the bridge ignores it.
- The bridge currently supports non-streaming only (`stream=false`).

## 🔥 Advanced Core Optimizations

- ⚡ **Parallel Tool Execution**: Concurrently executes multiple tools, boosting speed by 50% for complex tasks.
- 🌍 **Network Proxy Support**: Robust proxy integration for both Browser and Messaging channels.
- 🧠 **Light RAG & Infinite Dialogue**: Retrieval-based memory loading that solves context window limits.
> Note: The default workflow is single-agent. Subagents are used only when needed (e.g., long-running tasks or parallel research).

## 📦 Quick Start

```bash
# Install from source
git clone https://github.com/ls18166407597-design/nanobot.git
cd nanobot && pip install -e .

# Configuration & Launch
nanobot config check
nanobot doctor
nanobot gateway  # Starts the unified gateway (Telegram/Feishu)
```

## 📁 Optimized Workspace Architecture

```
workspace/
├── IDENTITY.md      # Core Mission (What are you)
├── SOUL.md          # Personality & Tone (Tone, Values)
├── AGENTS.md        # Technical Protocols (Hard rules for execution)
├── TOOLS.md         # Tool Recipes (Multi-step procedural guides)
├── HEARTBEAT.md     # Maintenance Hub (Proactive habits)
└── memory/          # Dynamically evolving context
```

## 🤝 Documentation

- ⚙️ **[Advanced Configuration Guide](docs/CONFIG_GUIDE.md)**
- 🏗️ **[Detailed Project Structure](docs/PROJECT_STRUCTURE.md)**

---
<p align="center">
  <em> Thanks for using ✨ nanobot! Your private senior executive secretary. </em>
</p>
