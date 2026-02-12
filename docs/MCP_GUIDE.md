# 工具专家手册

直接访问 Python 工具定义以获取基础参数，本手册仅存放高级组合技与实战策略。

## 🛠️ 核心 Recipe 组合

### 1. 深度环境探测
**策略**: 当由于界面变化导致自动化失效时，执行以下链路：
1. `mac_control(action="get_front_app_info")`: 确认焦点应用与状态。
2. `mac_vision(action="look_at_screen")`: 优先进行视觉语义分析，定位按钮和状态。
3. 当 `mac_vision` 不足以完成识别时，使用压缩截图（建议 `sips -Z 1024`）。
4. 仅在压缩图仍无法识别细节时，才使用原始全量截图。
5. `peekaboo(cmd="see")`: 在需要 UI 映射 ID 时再调用。
6. 回答首行固定标注 `视觉策略: L1|L2|L3`；若为 L2/L3，补一句降级原因。

### 2. 信息调研闭环
**策略**: 处理复杂调研任务时：
1. 先用 `tavily(action="search")` 做快速检索（默认）。
2. 失败时自动回退到 `duckduckgo(action="search")`。
3. 需要深度摘要时，用 `tavily(action="research")`。
4. 遇到页面渲染/交互/登录态/强反爬时，切到 `browser(action="search"|"browse")`。
5. `edit_file(...)`: 持续将结论增量写入 `workspace/report.md`。
6. **输出**: 给出结论时首行标注 `查询来源: ...`，并附文档路径。

### 3. 多端消息分发
**策略**: 
1. 查找 `workspace/scripts/contacts/contacts.json` 确认联系人平台。
2. 调用 `workspace/scripts/dispatch/smart_send.py` 进行协议适配发送。

---

## 🚦 常用工具速查表

| **类别** | **工具** | **描述** | **启动命令 (npx)** |
|---|---|---|---|
| **搜索** | **DuckDuckGo** | **国内友好**。无需信用卡，无需 Token，隐私保护。 | `npx -y @nickclyde/duckduckgo-mcp-server` |
| **地图** | **Baidu / Amap** | **国内最准**。支持经纬度、路线规划、周边搜索。 | `@baidumap/mcp-server-baidu-map` |
| **出行** | **12306 MCP** | 全国火车票余票、票价及经停站查询。 | `npx -y 12306-mcp` |
| **自动化** | **Puppeteer** | **超级浏览器**。具备点击、填表、截图能力。 | `npx -y @modelcontextprotocol/server-puppeteer` |
| **搜索 (备选)** | **Brave Search** | 极致检索。需要外卡验证。 | `npx -y @modelcontextprotocol/server-brave-search` |
| **办公 (备选)** | **Google Maps** | 全球通用。国内数据存在偏移/缺失。 | `npx -y @modelcontextprotocol/server-google-maps` |

---

## 🚦 执行准则
- **严禁幻觉**: 严禁在没有工具支撑的情况下编造数据。
- **结构化返回**: 必须解析 `ToolResult` 中的 `remedy` 字段以进行自我故障修复。

---

## 🏗️ 技术解读：MCP 在本项目中的定位
当前项目采用“**工具封装优先**”策略：
1. 模型优先调用项目内工具（如 `github`、`train_ticket`、`duckduckgo`）。
2. 这些工具在内部调用 MCP server，MCP 作为后端能力层。
3. 默认不向模型暴露通用 `mcp` 工具，避免参数漂移和协议误用。
- **静默机制**: 仅对无副作用的维护任务（如 RAG 向量化）使用 `SILENT_REPLY_TOKEN`。

---

## 工具配置文件位置

默认目录：`.home/tool_configs/`

规则：
- 读取与写入都统一使用 `.home/tool_configs/*.json`

常见配置文件：
- `gmail` -> `.home/tool_configs/gmail_config.json`
- `qq_mail` -> `.home/tool_configs/qq_mail_config.json`
- `github` -> `.home/tool_configs/github_config.json`
- `knowledge_base` -> `.home/tool_configs/knowledge_config.json`
- `weather` -> `.home/tool_configs/weather_config.json`
- `tavily` -> `.home/tool_configs/tavily_config.json`
- `tianapi` -> `.home/tool_configs/tianapi_config.json`
- `tushare` -> `.home/tool_configs/tushare_config.json`
- `feishu` -> `.home/tool_configs/feishu_config.json`
- `mcp` -> `.home/tool_configs/mcp_config.json`

说明（GitHub）：
- `github` 工具已切换为 MCP 后端。
- 需要在 `.home/tool_configs/mcp_config.json` 中配置 `servers.github`（command/args/env 等）。
- `github` 的 `setup` 动作仅用于保存 PAT 到 `.home/tool_configs/github_config.json`，运行时会自动注入 `GITHUB_TOKEN`（若 mcp_config 未显式提供）。
