# Nanobot 工作区指南 (Workspace Guide) 🐈

欢迎来到您的 Nanobot 个人工作区。这里是机器人存储所有持久化数据、自定义技能和自动化脚本的核心地带。

## 📂 目录结构 (Directory Structure)

### 1. `scripts/` - 共享脚本库
存放所有核心自动化 Python 脚本和数据文件。
- `smart_send.py`: 智能消息调度器，根据联系人别名自动选择 App 发送。
- `manage_contacts.py`: 联系人管理工具（增删改查）。
- `contacts.json`: 联系人数据库（别名、实名、App 映射）。
- `automate_*.py`: 针对特定 App（微信/Telegram）的底层 UI 自动化脚本。

### 2. `skills/` - 专业技能包
存放扩展机器人能力的 Markdown 配置文件。
- `automated-messaging/`: 专注于 WeChat/Telegram 的自动化发送。
- `computer-control/`: 通用的 macOS 系统级操控（键盘、鼠标、视觉）。

### 3. `memory/` - 智能记忆仓
存放机器人的长期记忆和每日运行日志。
- `MEMORY.md`: 核心长期记忆索引。
- `YYYY-MM-DD.md`: 每一天的详细运行记录。

## 📍 架构逻辑
- **核心框架 (`nanobot/`)**: 存放稳定的系统引擎代码。
- **用户空间 (`workspace/`)**: 存放您的私有数据、调优记录和特定领域的脚本。
- **Git 同步**: 整个目录已与 GitHub 仓库同步，确保您的资产永久安全。

---
> [!TIP]
> **秘书建议**：如果您编写了新的通用脚本，请将其放入 `workspace/scripts/`；如果您希望定义一个新的“任务领域”，请在 `workspace/skills/` 下新建文件夹并编写 `SKILL.md`。🐾
