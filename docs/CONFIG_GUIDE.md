# Nanobot Configuration Guide

This guide provides detailed instructions for configuring Nanobot's advanced tool suite.

## 🪄 Magic Onboarding (Recommended)

The easiest way to configure Nanobot is to use the **Magic Onboarding** feature. Simply start the agent and send your credentials in plain text.

1. Start the agent:
   ```bash
   nanobot agent
   ```
2. Send a message like:
   > "Setup my GitHub with token `your_token_here` and Gmail with `your_email@gmail.com` and app password `xxxx-xxxx-xxxx-xxxx`."

Nanobot will automatically detect the credentials, verify them, and save the configuration for you.

---

## ⚙️ Manual Configuration

If you prefer to configure tools manually, you can edit the JSON files in `~/.nanobot/`.

### 📧 Gmail
- **File**: `~/.nanobot/gmail_config.json`
- **Fields**:
  - `email`: Your Gmail address.
  - `app_password`: A 16-character App Password generated from your Google Account settings.
  - `imap_server`: (Optional) Defaults to `imap.gmail.com`.
  - `smtp_server`: (Optional) Defaults to `smtp.gmail.com`.

### 🐙 GitHub
- **File**: `~/.nanobot/github_config.json`
- **Fields**:
  - `personal_access_token`: A GitHub PAT with `repo` and `workflow` scopes.
  - `username`: (Optional) Your GitHub username.

### 📚 Knowledge Base (Obsidian)
- **File**: `~/.nanobot/knowledge_config.json`
- **Fields**:
  - `vault_path`: The absolute path to your local Markdown/Obsidian vault.

### 🔍 Web Search (Brave)
- **File**: `~/.nanobot/web_config.json`
- **Fields**:
  - `brave_api_key`: Your Brave Search API key.

### 🤖 LLM Providers
- **File**: `~/.nanobot/config.json`
- **Description**: Configure API keys and base URLs for your models in the `providers` array.
- **Example Configuration**:
  ```json
  "providers": [
    {
      "name": "local-gemini",
      "model": "gemini-3-flash",
      "baseUrl": "http://127.0.0.1:8045/v1",
      "apiKey": "YOUR_GEMINI_API_KEY"
    },
    {
      "name": "qwen-7b",
      "model": "Qwen/Qwen2.5-7B-Instruct",
      "baseUrl": "https://api.siliconflow.cn/v1",
      "apiKey": "YOUR_SILICONFLOW_API_KEY"
    }
  ]
  ```
- **Fields Reference**:
  - `name`: Internal name used for routing (keep consistent with `SOUL.md` expert selection).
  - `model`: The raw model name from the provider.
  - `baseUrl`: The base URL for the API (must be OpenAI-compatible).
  - `apiKey`: Your secret access token.

### 🧠 Brain / Intelligence Configuration
- **File**: `~/.nanobot/config.json` (under `brain` field)
- **Fields**:
  - `auto_summarize`: (bool) Enable auto-summarization for infinite context. Default `true`.
  - `summary_threshold`: (int) Message count threshold to trigger summarization. Default `40`.
  - `safety_guard`: (bool) Enable LLM safety guard for shell commands. Default `true`.

---

## 🛡️ Security Note
Your credentials are **never** uploaded to any server. They are stored strictly on your local machine in the `~/.nanobot/` directory. For enhanced security, you can set `"restrictToWorkspace": true` in your main `config.json`.
