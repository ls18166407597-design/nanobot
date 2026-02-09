# Nanobot Advanced Configuration Guide ⚙️

This guide provides instructions on how to configure your Nanobot secretary using the new CLI suite and automated workflows.

## 🚀 CLI-First Configuration (Recommended)

The easiest and safest way to manage your settings is via the built-in `nanobot config` command, which prevents syntax errors associated with manual JSON editing.

## ✅ Minimum Viable Path (5-minute smoke test)
1. Set your model and API key.  
2. Run `nanobot config check` to validate JSON syntax (not full semantic validation).  
3. Try `nanobot agent -m "Give me 3 things to do today"` to validate a full roundtrip.  
4. If you want desktop control, set `tools.mac.confirmMode` to `warn` or `require`.  

### 1. Basic Commands
- **View current configuration**: `nanobot config list`
- **Set a parameter**: `nanobot config set agents.defaults.model "gpt-4o"`
- **Validate configuration (JSON only)**: `nanobot config check`
> `nanobot config set` accepts JSON values (e.g., `true/false`, numbers, arrays, objects, `null`).

### 2. Common Parameter Paths
- **LLM Model**: `agents.defaults.model`
- **Web Proxy**: `tools.web.proxy` (e.g., "http://127.0.0.1:1087")
- **Safety Guard**: `brain.safetyGuard` (true/false)
- **macOS Confirm Mode**: `tools.mac.confirmMode` (off/warn/require)

---

## 📂 Workspace Management

Nanobot's "Soul and Memory" are stored in the workspace.
- **Default Location**: `./workspace` (Repository local folder)
- **Customization**: To change the primary workspace, run `nanobot config set agents.defaults.workspace "/your/path"`.

**Data directory override**:
- Use `NANOBOT_HOME` to override the data directory (defaults to local `.nanobot`).
- If you start with `start.sh`, the data directory is `./.home`.

**Workspace Hierarchy**:
1. `IDENTITY.md`: Core mission and role.
2. `SOUL.md`: Tone, values, and personality.
3. `AGENTS.md`: Technical execution protocols.
4. `TOOLS.md`: Tool Recipes and procedural guides.

---

## 🛠️ Core Service Setup

### 1. Magic Onboarding
Run `nanobot onboard` for a guided setup. Alternatively, you can set keys via `nanobot config set ...` or edit the config file manually.

### 2. Multi-Channel Access (Gateway)
Central config: `config.json` (Located in the local `.nanobot/` folder or the directory defined by `NANOBOT_HOME`)
- **Telegram**: Configure `token` under `channels.telegram`.
- **Feishu**: Configure `appId` and `appSecret` under `channels.feishu`.

### 3. Network Proxy
If you encounter timeouts with Google search or Telegram, ensure the proxy is set:
```bash
nanobot config set tools.web.proxy "http://127.0.0.1:1087"
```

### 4. Antigravity OAuth + Local Bridge (OpenAI-Compatible)

If you want to login with Google OAuth but still call via an OpenAI-compatible API (lowest friction), use the local bridge:

1. OAuth login (creates `antigravity_auth.json`):
```
python3 scripts/antigravity_oauth_login.py --set-default-model
```

2. Start the bridge service:
```
python3 scripts/antigravity_bridge.py --port 8046
```

3. Point nanobot to the local bridge:
```
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
Note: `browser` actions must be delegated to subagents via `spawn` in the main agent workflow.

## 🧾 Logs
Key tool execution events are recorded in `audit.log` under `NANOBOT_HOME` for tracing and latency analysis.
Gateway runtime logs are written to `gateway.log` under `NANOBOT_HOME`.

---
<p align="center">
  <em> Thanks for using ✨ nanobot! Your private senior executive secretary. 🐾</em>
</p>
