# 工具使用索引

本文件只描述工具分工与配置位置，不承载人格或执行铁律。

## 联网工具分工
- `tavily`：默认检索入口（快速、结构化）。
- `browser`：页面渲染/交互/登录态场景。
- `mcp`：外部扩展入口，仅在用户明确要求或前两者失败后使用。

## 常用组合
1. 调研闭环：`tavily.search -> tavily.research -> browser.search/browse -> mcp`（按需）
2. 屏幕任务：`mac_control -> mac_vision -> 压缩图 -> 原图`
3. 消息发送：先查 `workspace/scripts/contacts/contacts.json`，再调用消息工具或分发脚本

## 配置文件目录
- 统一目录：`.home/tool_configs/`
- `gmail` -> `gmail_config.json`
- `qq_mail` -> `qq_mail_config.json`
- `github` -> `github_config.json`
- `knowledge_base` -> `knowledge_config.json`
- `weather` -> `weather_config.json`
- `tavily` -> `tavily_config.json`
- `tianapi` -> `tianapi_config.json`
- `tushare` -> `tushare_config.json`
- `feishu` -> `feishu_config.json`
- `mcp` -> `mcp_config.json`
