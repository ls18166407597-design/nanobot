---
name: cron
description: 安排提醒和定期任务。
---

# 定时任务 (Cron)

使用 `cron` 工具来安排提醒或定期任务。

## 两种模式

1. **提醒 (Reminder)** - 直接发送消息给用户
2. **任务 (Task)** - 消息是任务描述，Agent 执行并发送结果

## 示例

固定提醒:
```
cron(action="add", message="该休息一下了！", every_seconds=1200)
```

动态任务 (Agent 每次执行):
```
cron(action="add", message="检查 HKUDS/nanobot GitHub star 数并报告", every_seconds=600)
```

列出/移除:
```
cron(action="list")
cron(action="remove", job_id="abc123")
```

## 时间表达式

| 用户说 | 参数 |
|-----------|------------|
| 每 20 分钟 | every_seconds: 1200 |
| 每小时 | every_seconds: 3600 |
| 每天早上 8 点 | cron_expr: "0 8 * * *" |
| 工作日下午 5 点 | cron_expr: "0 17 * * 1-5" |
