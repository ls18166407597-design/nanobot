---
name: automated-messaging
description: 桌面消息自动化专家。通过集成脚本实现微信 (WeChat)、Telegram 及其他主流通讯工具的联系人管理、智能路由及自动消息发送。
---

# 桌面消息自动化 (Desktop Messenger) 🐈

此技能旨在让 Nanobot 具备原生级别的 macOS 消息处理能力，通过调用底层自动化脚本，实现与微信、Telegram 等联系人的高效触达。

## 💡 核心逻辑 (Core Logic)

为了确保执行成功，请遵循以下闭环路径：

```mermaid
graph TD
    A[收到消息指令] --> B{已知联系人?}
    B -- 否 --> C[读取 USER.md 索引或 contacts.json]
    B -- 是 --> D[匹配别名与 App]
    C --> D
    D --> E[运行 smart_send.py 发送]
    E --> F[确认发送状态并汇报]
```

## 🛠️ 指令库 (Command Library)

### 1. 发送消息 (Primary Send)
直接调度 `smart_send.py` 进行自动化发送。
```bash
python3 scripts/smart_send.py "别名" "消息内容"
```

### 2. 获取/管理通讯录 (Contact Management)
读取或修改本地 `contacts.json` 数据库。
```bash
# 列出所有已存联系人（首选步骤）
python3 scripts/manage_contacts.py list

# 新增联系人映射
python3 scripts/manage_contacts.py add "别名" "App内实名" WeChat/Telegram
```

## 📂 数据架构 (Data Architecture)

- **核心数据库**: `scripts/contacts.json` (记录别名与 App 的映射关系)。
- **路径索引**: 详细的数据位置已在 `USER.md` 的 **## 📂 数据索引** 中建立常驻链接。

---
> [!TIP]
> **秘书建议**：在进行大规模群发前，建议先运行 `list` 命令确认所有联系人的别名已正确录入，以确保发送路径 100% 精准。🐾
