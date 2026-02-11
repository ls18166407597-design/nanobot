# CLI验收清单

用于每次修改核心链路（`loop`、`commands`、`runtime_commands`、`channels`、`tools`）后的快速回归。

## 0. 前置条件

- 在项目根目录执行命令：`/Users/liusong/Downloads/nanobot`
- 使用项目内数据目录：`NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home`
- Python 运行环境可用：`.venv/bin/nanobot`

## 1. 基础健康检查

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home .venv/bin/nanobot check --quick
```

通过标准：
- Python、Git、Network、Model API 为 `OK`

## 2. 状态快照检查

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home .venv/bin/nanobot status --snapshot
```

通过标准：
- `Config` 和 `Workspace` 为存在状态
- `Model` 显示为当前配置模型
- `Provider Registry` 显示正常（数量与预期一致）

## 3. 工具注册检查

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home .venv/bin/nanobot tools
```

通过标准：
- 命令可执行且工具列表可完整渲染
- `confirm mode` 字段可见

## 4. 日志读取检查

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home .venv/bin/nanobot logs --lines 50
```

通过标准：
- 能读到 `gateway.log`
- 无命令级异常退出

## 5. 网关生命周期检查

### 5.1 停止

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home .venv/bin/nanobot stop --timeout 8
```

通过标准：
- 输出 `Gateway stopped` 或等价成功信息

### 5.2 启动

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home ./start.sh
```

通过标准：
- 输出 `Starting nanobot gateway`
- 无启动崩溃，后续 `status --snapshot` 显示 `Gateway: running`

### 5.3 重启

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home .venv/bin/nanobot restart --timeout 8
```

通过标准：
- 可先停后起，最终 `Gateway: running`

### 5.4 冲突保护（可选）

在网关已运行时执行：

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home .venv/bin/nanobot gateway --port 18790
```

通过标准：
- 正确提示已有实例运行并退出，不应出现僵尸进程

## 6. 健康命令检查

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home .venv/bin/nanobot health
```

通过标准：
- 命令返回 `Health check passed`
- 若有 `WARN`，需确认是否为历史噪音（例如旧 `audit` 错误）

## 7. 自动化回归测试

```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home ./.venv/bin/pytest -q
```

通过标准：
- 测试通过，或仅存在明确已知且可接受的 `skip`

说明：
- 若不设置 `NANOBOT_HOME`，在某些环境下可能写入 `~/.nanobot` 导致权限失败，属于环境问题而非功能回归。

## 8. 失败处理建议

- `gateway.pid` 残留：先执行 `nanobot stop`，再检查 PID 是否真实存在。
- 网络异常：优先检查本机代理、DNS、目标 API 可达性。
- 模型连通性异常：检查 `config.json` 的模型名、`api_base`、密钥是否匹配。
- Telegram异常：检查 `bot token`、代理配置、轮询日志中的 HTTP 错误。

## 9. 探索任务回包检查（新增）

适用场景：`mac_control`/`mac_vision`/`exec` 组合探索（例如“看看这个应用有什么功能”）。

检查方式：
1. 发送一条开放式探索任务。  
2. 在 `audit.log` 中确认工具调用量受控（不会无限增长）。  
3. 最终回包应为“执行摘要/结论”，不应出现“已处理但无具体内容”。

通过标准：
- 在预算触发或上限触发时，系统返回强制总结文本。  
- 用户侧可拿到明确可读结果，而不是空回复兜底。
