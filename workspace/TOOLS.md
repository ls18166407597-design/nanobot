# 工具使用索引

本文件只描述工具分工与配置位置，不承载人格或执行铁律。

## 路由总原则
- 先专用后通用：能用领域工具就不要先走通用搜索。
- 单子问题单通道：同一步尽量只用一类联网能力，避免并行混用导致噪声。
- 对用户展示“业务来源”（如 `12306`、`GitHub`、`DuckDuckGo`、`Browser`），不展示实现细节（如 `MCP`/SDK）。

## 联网工具分工
- `train_ticket`：火车票查询能力（优先使用）。
- `tavily`：API 检索能力。
- `duckduckgo`：通用网页检索能力（后端封装，作为信息检索第二优先级）。
- `browser`：页面渲染/交互能力。
- 具体选择顺序由运行时 ToolPolicy 决定，本文件不重复定义策略细节。

## 邮件工具分工
- `mail`：统一邮件入口（优先使用）。
- `gmail`：Gmail 协议实现（mail 内部路由可调用）。
- `qq_mail`：QQ 邮箱协议实现（mail 内部路由可调用）。

## 技能-工具映射
- `automated-messaging` -> `message`, `mac_control`, `mac_vision`, `exec`
- `computer-control` -> `mac_control`, `mac_vision`, `exec`
- `github` -> `github`, `read_file`, `write_file`, `edit_file`
- `train-ticket` -> `train_ticket`
- `mail` -> `mail`（内部路由 `gmail/qq_mail`）
- `cron` -> `cron`, `task`, `exec`
- `system-health-check` -> `exec`, `read_file`, `list_dir`
- `project-sentinel` -> `exec`, `read_file`, `write_file`
- `html-cleanup` -> `read_file`, `write_file`, `edit_file`
- `clawhub` -> `skills`, `exec`

## 常用组合
1. 调研闭环：按 ToolPolicy 选用联网工具；必要时结合 `read_file/edit_file` 形成结果闭环
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
- `train_ticket` -> `mcp_config.json`（读取 `servers.12306`）
- `duckduckgo` -> `mcp_config.json`（读取 `servers.duckduckgo`）
- `github` -> `mcp_config.json`（读取 `servers.github`）
