# 工具专家手册 (Recipes)

直接访问 Python 工具定义以获取基础参数，本手册仅存放高级组合技与实战策略。

## 🛠️ 核心 Recipe 组合

### 1. 深度环境探测 (Cognitive Insight)
**策略**: 当由于界面变化导致自动化失效时，执行以下链路：
1. `mac_control(action="get_front_app_info")`: 确认焦点应用与状态。
2. `mac_vision(action="look_at_screen")`: 进行视觉语义分析，寻找“失踪”的按钮。
3. `peekaboo(cmd="see")`: 获取最新的 UI 映射 ID。

### 2. 信息调研闭环 (Research & Doc)
**策略**: 处理复杂调研任务时：
1. `browser(action="search")`: 多源信息搜集。
2. `browser(action="browse")`: 深入阅读高价值网页。
3. `edit_file(...)`: 持续将结论增量写入 `workspace/report.md`。
4. **输出**: 为老板提供结论摘要及文档路径。

### 3. 多端消息分发 (Smart Send)
**策略**: 
1. 查找 `workspace/scripts/contacts.json` 确认联系人平台。
2. 调用 `workspace/scripts/smart_send.py` 进行协议适配发送。

---

## 🚦 执行准则
- **严禁幻觉**: 严禁在没有工具支撑的情况下编造数据。
- **结构化返回**: 必须解析 `ToolResult` 中的 `remedy` 字段以进行自我故障修复。
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
