# nanobot: Ultralight Desktop AI Secretary (Advanced)

<div align="center">
  <p align="right">
    <strong>English</strong> | <a href="README.md">简体中文</a>
  </p>
  <h1>nanobot: Secretary Edition</h1>
</div>

---

## 📁 Separated Architecture (V2.0)

We have refactored the project into a "Triad" isolated architecture for long-term stability:

- **`nanobot/`** (Engine): Immutable core source code and base skills.
- **`workspace/`** (Brain): Your personalized prompts, skills, scripts, and memory.
- **`.home/`** (Runtime): Persistent configurations and logs.

## 🌟 Key Features

- **Agentic Protocols**: Transparent delegation, ask on failure, and result verification.
- **macOS Native Vision**: AppKit-based app identification and OCR.
- **Smart Workspace**: Clean separation between system logic and user assets.

## 🤝 Documentation (Chinese)

- ⚙️ **[Configuration Guide](docs/配置指南.md)**
- 🗺️ **[Roadmap](docs/路线图.md)**
- 🏗️ **[Project Structure](docs/项目结构.md)**

## Core Refactor Snapshot (2026-02-11)

This round focused on reducing core complexity and hardening contracts:

- Turn execution extracted from `AgentLoop` to `nanobot/agent/turn_engine.py`.
- Provider failover extracted to `nanobot/agent/provider_router.py`.
- Default tool wiring extracted to `nanobot/agent/tool_bootstrapper.py`.
- Session switching/listing extracted to `nanobot/session/service.py`.
- Telegram formatting/media logic extracted to
  `nanobot/channels/telegram_format.py` and `nanobot/channels/telegram_media.py`.
- Core contracts documented in `ARCHITECTURE.md`, with contract tests in
  `nanobot/tests/test_contracts.py`.

---
<p align="center">
  <em> Thank you for using ✨ nanobot! Your advanced administrative secretary. 🐾</em>
</p>
