---
name: mail
description: 使用统一 mail 工具执行邮箱操作（status/list/read/send/setup），自动路由 gmail/qq_mail。
metadata:
  {
    "nanobot": {
      "tags": ["mail", "gmail", "qq_mail"],
      "scope": "business"
    }
  }
---

# 邮件操作技能 (Mail)

当用户要求查收件箱、读邮件、发邮件时，优先使用本技能。

## 适用场景
- 查看邮箱状态（总数/未读）。
- 列出最近邮件并读取指定邮件。
- 发送邮件。
- 首次配置邮箱账号。

## 执行规则
1. 统一使用 `mail` 工具，不直接优先调用 `gmail/qq_mail`。
2. provider 默认 `auto`；用户明确指定时再传 `provider="gmail"` 或 `provider="qq_mail"`。
3. `send` 动作必须确认 `to/subject/body` 三要素完整。
4. `read` 动作必须先 `list` 获取 `email_id`，再读取。
5. 回复首行查询来源由系统自动注入；邮件类结果保持简洁结构化。

## 推荐调用
- 查看状态：
  `mail(action="status")`
- 列最近邮件：
  `mail(action="list", limit=10)`
- 读取邮件：
  `mail(action="read", email_id="123")`
- 发送邮件：
  `mail(action="send", to="a@example.com", subject="主题", body="正文")`
- 配置邮箱：
  `mail(action="setup", setup_email="xxx@gmail.com", setup_password="app_password")`

## 失败处理
- 未配置：提示使用 `setup` 动作完成配置。
- 参数缺失：明确指出缺哪个字段。
- 认证失败：提示检查应用专用密码/授权码与 IMAP/SMTP 开关。
