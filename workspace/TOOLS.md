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
2. 需要深度摘要时，用 `tavily(action="research")`。
3. 遇到页面渲染/交互/登录态/强反爬时，切到 `browser(action="search"|"browse")`。
4. 一路失败时执行回退：`tavily` <-> `browser` 互为备用。
5. `edit_file(...)`: 持续将结论增量写入 `workspace/report.md`。
6. **输出**: 给出结论时标注 `联网策略: API|Browser|Fallback`，并附文档路径。

### 3. 多端消息分发
**策略**: 
1. 查找 `workspace/scripts/contacts/contacts.json` 确认联系人平台。
2. 调用 `workspace/scripts/dispatch/smart_send.py` 进行协议适配发送。

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
