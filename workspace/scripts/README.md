# workspace/scripts 入口索引

本目录按功能分域组织脚本。建议在项目根目录 `/Users/liusong/Downloads/nanobot` 执行。

## 通用约定

- Python 入口建议使用：`.venv/bin/python`
- 默认数据目录建议固定：`NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home`
- 通讯录文件：`/Users/liusong/Downloads/nanobot/workspace/scripts/contacts/contacts.json`

## contacts（联系人管理）

入口脚本：
- `contacts/manage_contacts.py`

示例：
```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home \
.venv/bin/python workspace/scripts/contacts/manage_contacts.py list

NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home \
.venv/bin/python workspace/scripts/contacts/manage_contacts.py add boss "张总" Telegram --note "工作联系人"

NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home \
.venv/bin/python workspace/scripts/contacts/manage_contacts.py validate
```

## dispatch（统一分发）

入口脚本：
- `dispatch/smart_send.py`

示例：
```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home \
.venv/bin/python workspace/scripts/dispatch/smart_send.py boss "老板，已处理完成"

NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home \
.venv/bin/python workspace/scripts/dispatch/smart_send.py --all "群发通知：今天19:00开会" --app Telegram
```

## mail（邮件巡检与已读处理）

该组脚本已归档到技能目录：
- `workspace/skills/mail/scripts/check_emails.py`
- `workspace/skills/mail/scripts/mark_gmail_read.py`
- `workspace/skills/mail/scripts/mark_qq_read.py`

## telegram（Telegram 自动化）

入口脚本：
- `telegram/automate_telegram_keyboard_final.py`
- `telegram/automate_telegram_blind.py`
- `telegram/tg_checkin_task_blind.py`
- `telegram/tg_water_task.py`
- `telegram/tg_water_task_blind.py`

示例：
```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home \
.venv/bin/python workspace/scripts/telegram/automate_telegram_keyboard_final.py --contact "Alice" --message "你好"

NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home \
.venv/bin/python workspace/scripts/telegram/automate_telegram_keyboard_final.py --info

NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home \
.venv/bin/python workspace/scripts/telegram/tg_checkin_task_blind.py
```

## wechat（微信自动化）

入口脚本：
- `wechat/automate_wechat_keyboard_final.py`

示例：
```bash
NANOBOT_HOME=/Users/liusong/Downloads/nanobot/.home \
.venv/bin/python workspace/scripts/wechat/automate_wechat_keyboard_final.py --contact "张三" --message "收到"
```

## vision（图片压缩优化）

入口脚本：
- `vision/vision_optimizer.sh`

示例：
```bash
bash workspace/scripts/vision/vision_optimizer.sh /tmp/in.png /tmp/out.png 1024
```

## html（HTML 清洗）

该脚本已归档到技能目录：
- `workspace/skills/html-cleanup/scripts/clean_html.py`
