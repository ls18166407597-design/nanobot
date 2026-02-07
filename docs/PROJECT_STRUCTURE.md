# Nanobot 项目结构说明 🏗️

这是 Nanobot 项目的全部文件布局。

```
nanobot/
├── .nanobot/            # [配置中心] (位于用户主目录 ~/.nanobot)
│   ├── config.json      #    - 全局配置文件 (API Key, 模型设置)
│   └── sessions/        #    - 对话历史记录数据库
│
├── memory/              # [预留] 项目级记忆 (目前为空，用于扩展本地向量库)
│
├── nanobot/                 # 🧠 核心源码
│   ├── agent/               #    - [核心] 智能体逻辑 (大脑)
│   │   ├── loop.py          #      - 主循环 (接收消息 -> 思考 -> 工具 -> 回复)
│   │   ├── context.py       #      - 上下文管理 (长短期记忆拼接)
│   │   ├── models.py        #      - 模型适配器 (SiliconFlow, Local Gemini)
│   │   ├── memory.py        #      - 记忆检索模块 (RAG)
│   │   └── tools/           #    - [工具箱] 内置 Python 工具
│   │       ├── mac_vision.py#      - [新增] macOS 原生视觉 (OCR & 坐标)
│   │       ├── browser.py   #      - [核心] 本地浏览器工具 (Playwright)
│   │       ├── codebase.py  #      - 代码库搜索工具
│   │       ├── file.py      #      - 文件读写工具
│   │       └── ...
│   ├── channels/            #    - [通讯] 消息网关
│   │   ├── telegram.py      #      - Telegram 机器人适配器
│   │   └── discord.py       #      - Discord 机器人适配器
│   ├── cli/                 #    - [终端] 命令行工具 (nanobot onboard/agent)
│   └── brain/               #    - [思考] 决策逻辑与安全守卫
│
├── workspace/               # 📂 本地工作区 (灵魂与记忆)
│   ├── SOUL.md              #    - [核心] 角色设定 (Soul) - 定义 "你是谁"
│   ├── IDENTITY.md          #    - [核心] 身份设定 (Persona) - 定义 "语气与人设"
│   ├── TOOLS.md             #    - [文档] 工具手册 - 告诉 Agent 如何使用工具
│   ├── skills/              #    - [技能] 外部技能库 (OpenClaw)
│   │   └── peekaboo/        #      - [新增] 全能电脑控制 (视觉+动作)
│   └── memory/              #    - [记忆] 长期记忆库 (对话日志与知识)
│
├── docs/                    # 📄 项目文档
│   ├── PROJECT_STRUCTURE.md #    - 本文件
│   ├── CONFIG_GUIDE.md      #    - 配置指南
│   └── ROADMAP.md           #    - 开发路线图
│
├── README.md                # 📘 项目介绍 (中文)
├── README_EN.md             # 📘 Project Readme (English)
├── pyproject.toml           # ⚙️ Python 依赖与配置
└── Dockerfile               # 🐳 容器化构建文件
```

---

## 🔑 关键文件速查

| 文件/目录 | 作用 |
| :--- | :--- |
| **`nanobot/agent/loop.py`** | 整个系统的中枢神经，控制思考流程。 |
| **`workspace/SOUL.md`** | 修改此文件可改变 AI 的性格和核心指令。 |
| **`workspace/skills/peekaboo`** | 赋予 AI 操作电脑鼠标键盘的能力。 |
| **`nanobot/agent/tools/mac_vision.py`** | 赋予 AI 看清屏幕并识别坐标的能力。 |
