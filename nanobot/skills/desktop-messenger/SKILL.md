---
name: desktop-messenger
description: 通过查看本地通讯录，向微信 (WeChat) 或 Telegram 联系人发送消息。支持发送、联系人管理（增删改查）和智能应用路由。
---

# 桌面消息技能 (Desktop Messenger Skill)

此技能允许 Nanobot 通过查看本地通讯录，查找联系人的首选应用程序，从而向微信或 Telegram 上的联系人发送消息。

## 用法 (Usage)

**1. 查找或管理联系人:**
在发送消息前，通常需要先获取联系人的 App 和别名。
```bash
python3 nanobot/scripts/manage_contacts.py list
```

**2. 发送消息:**
通过 `run_command` 调用 `smart_send.py`。
```bash
python3 nanobot/scripts/smart_send.py "联系人别名" "消息内容"
```

## 工作原理

1.  **发送**: 技能调用 `scripts/smart_send.py`。
2.  **管理**: 技能调用 `scripts/manage_contacts.py` 执行 `add` (添加), `remove` (删除), 或 `list` (列出)。
3.  脚本读写 `scripts/contacts.json`。
4.  根据路由结果，调度自动化脚本进行发送。

## 配置

编辑 `nanobot/scripts/contacts.json` 以手动添加新联系人:

```json
{
  "alias": {
    "name": "App 中的真实显示名称",
    "app": "WeChat"  // 或 "Telegram"
  }
}
```

## 实现细节

通过程序或 CLI 调用:

```bash
# 发送
python3 scripts/smart_send.py "联系人别名" "消息内容"

# 管理
python3 scripts/manage_contacts.py list
python3 scripts/manage_contacts.py add "alias" "Real Name" WeChat --note "Description"
python3 scripts/manage_contacts.py remove "alias"
```
