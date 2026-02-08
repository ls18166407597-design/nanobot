# Nanobot Advanced Configuration Guide ⚙️

This guide provides instructions on how to configure your Nanobot secretary using the new CLI suite and automated workflows.

## 🚀 CLI-First Configuration (Recommended)

The easiest and safest way to manage your settings is via the built-in `nanobot config` command, which prevents syntax errors associated with manual JSON editing.

### 1. Basic Commands
- **View current configuration**: `nanobot config list`
- **Set a parameter**: `nanobot config set agents.defaults.model "gpt-4o"`
- **Validate configuration**: `nanobot config check`

### 2. Common Parameter Paths
- **LLM Model**: `agents.defaults.model`
- **Web Proxy**: `tools.web.proxy` (e.g., "http://127.0.0.1:1082")
- **Safety Guard**: `brain.safetyGuard` (true/false)

---

## 📂 Workspace Management

Nanobot's "Soul and Memory" are stored in the workspace.
- **Default Location**: `./workspace` (Repository local folder)
- **Customization**: To change the primary workspace, run `nanobot config set agents.defaults.workspace "/your/path"`.

**Workspace Hierarchy**:
1. `IDENTITY.md`: Core mission and role.
2. `SOUL.md`: Tone, values, and personality.
3. `AGENTS.md`: Technical execution protocols.
4. `TOOLS.md`: Tool Recipes and procedural guides.

---

## 🛠️ Core Service Setup

### 1. Magic Onboarding
Run `nanobot onboard` for a guided setup. Alternatively, you can directly send API keys to the agent during a session, and it will configure itself automatically.

### 2. Multi-Channel Access (Gateway)
Central config: `~/.nanobot/config.json`
- **Telegram**: Configure `token` under `channels.telegram`.
- **Feishu**: Configure `appId` and `appSecret` under `channels.feishu`.

### 3. Network Proxy
If you encounter timeouts with Google search or Telegram, ensure the proxy is set:
```bash
nanobot config set tools.web.proxy "http://127.0.0.1:1087"
```

## 🛡️ System Diagnostics (Doctor)
If you suspect issues with vision or browser tools, run:
```bash
nanobot doctor
```
It automatically checks:
- Python environment & `PYTHONPATH`
- Playwright browser drivers
- macOS Vision permissions
- Network connectivity

---
<p align="center">
  <em> Thanks for using ✨ nanobot! Your private senior executive secretary. 🐾</em>
</p>
