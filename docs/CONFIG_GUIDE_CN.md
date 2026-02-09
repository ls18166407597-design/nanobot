# Nanobot 高级配置指南 ⚙️

本指南介绍了如何使用全新的 CLI 工具和自动工作流来配置您的 Nanobot 秘书。

## 🚀 CLI 优先配置 (推荐)

现在管理配置最简单、最安全的方法是使用内置的 `nanobot config` 指令。这可以避免手动编辑 JSON 导致的语法错误。

## ✅ 最小可用路径 (5 分钟跑通)
1. 设置模型与 API Key。  
2. 运行 `nanobot config check` 仅检查 JSON 语法是否正确（不做完整语义校验）。  
3. 启动 `nanobot agent -m "帮我列出今天要做的 3 件事"` 验证一次完整对话。  
4. 如需工具权限（如桌面控制），将 `tools.mac.confirmMode` 设为 `warn` 或 `require`。  

### 1. 基础配置
- **查看当前设置**: `nanobot config list`
- **修改参数**: `nanobot config set agents.defaults.model "gpt-4o"`
- **检查有效性（仅 JSON）**: `nanobot config check`
> `nanobot config set` 支持 JSON 值（如 `true/false`、数字、数组、对象、`null`）。

### 2. 常用参数路径
- **核心模型**: `agents.defaults.model`
- **网络代理**: `tools.web.proxy` (例如 "http://127.0.0.1:1087")
- **推理开关**: `brain.reasoning` (true/false) - 开启后强制使用 `<think>` 推理标签
- **安全守卫**: `brain.safetyGuard` (true/false)
- **macOS 工具确认**: `tools.mac.confirmMode` (off/warn/require)

---

## 📂 工作区管理 (Workspace)

Nanobot 的“灵魂与记忆”存储在工作区中。
- **默认位置**: `./workspace` (仓库本地目录)
- **迁移建议**: 如果您希望将配置保存在其他位置，请通过 `nanobot config set agents.defaults.workspace "/your/path"` 修改。

**数据目录覆盖**:
- 通过环境变量 `NANOBOT_HOME` 覆盖数据目录（默认为项目下的 `.nanobot`）。
- 若通过 `start.sh` 启动，数据目录为 `./.home`。

**配置文件层级**:
1. `IDENTITY.md`: 核心使命定义。
2. `SOUL.md`: 语气、价值观与性格。
3. `AGENTS.md`: 技术执行硬协议。
4. `TOOLS.md`: 工具使用秘籍 (Recipes)。

---

## 🛠️ 核心服务配置

### 1. 魔法初始化 (Onboarding)
运行 `nanobot onboard` 启动引导式设置。或者使用 `nanobot config set ...` / 手动编辑配置文件写入 Key。

### 2. 多渠道接入 (Gateway)
配置文件：`config.json` (默认位于项目下的 `.nanobot/`，或 `NANOBOT_HOME` 指定目录)
- **Telegram**: 在 `channels.telegram` 下配置 `token`。
- **飞书 (Feishu)**: 在 `channels.feishu` 下配置 `appId` 和 `appSecret`。

### 4. Antigravity OAuth + 本地桥接（OpenAI-Compatible）

如果你希望用 Google OAuth 登录，但仍通过 OpenAI 兼容接口调用（最省事、兼容性最好），可使用本地桥接：

1. OAuth 登录（生成 `antigravity_auth.json`）：
```
python3 scripts/antigravity_oauth_login.py --set-default-model
```

2. 启动桥接服务：
```
python3 scripts/antigravity_bridge.py --port 8046
```

3. 配置 nanobot 使用本地桥接：
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

说明：
- `api_key` 只是占位，桥接会忽略它。
- 目前桥接仅支持非流式（`stream=false`）。

### 3. 网络代理 (Proxy)
如果您在国内环境使用 Google 搜索或 Telegram，务必设置代理：
```bash
nanobot config set tools.web.proxy "http://127.0.0.1:1087"
```

## 🛡️ 系统诊断 (Doctor)
如果您怀疑某些功能（如视觉或浏览器）无法正常工作，请运行：
```bash
nanobot doctor
```
它会自动检查：
- Python 环境与 `PYTHONPATH`
- Playwright 浏览器驱动
- macOS Vision 权限
- 网络连通性
注意：`browser` 相关操作需通过 `spawn` 子智能体执行，主智能体禁止直接调用。

## 🧾 审计与日志 (Logs)

Nanobot 提供了便捷的日志查看工具，无需手动寻找文件：
- **查看网关日志**: `nanobot logs`
- **追踪最新日志**: `nanobot logs -f`
- **查看审计记录**: `nanobot logs --audit`

日志文件物理路径：
- `gateway.log`: 数据目录 `NANOBOT_HOME` 下（默认 `./.nanobot/` 或 `~/.nanobot/`）。
- `audit.log`: 存储在数据目录 `NANOBOT_HOME` 下。

---
<p align="center">
  <em> 感谢您使用 ✨ nanobot！您的私人高级行政秘书。🐾</em>
</p>
