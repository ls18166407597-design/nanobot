# Nanobot 项目结构说明 🏗️

这是 Nanobot (秘书进阶版) 的完整文件布局与逻辑分层。

## 📁 目录一览

```
nanobot/
├── .nanobot/            # [配置与数据中心] (默认位于项目根目录，可通过 NANOBOT_HOME 环境变量自定义)
│   ├── config.json      #    - 全局配置文件 (API Key, 代理, 渠道)
│   ├── sessions/        #    - 会话历史与短期记忆库
│   ├── gateway.log      #    - 网关运行日志 (NANOBOT_HOME/gateway.log)
│   └── audit.log        #    - 审计日志 (NANOBOT_HOME/audit.log)
│
├── nanobot/                 # 🧠 核心源码 (核心包)
│   ├── agent/               #    - [大脑] 智能体循环与上下文管理
│   │   ├── loop.py          #      - 观察-思考-行动-评估循环
│   │   ├── context_guard.py #      - [组件] 上下文卫士 (Token 压缩与监控)
│   │   ├── subagent.py      #      - 子智能体管理逻辑
│   │   └── tools/           #      - 内置核心工具 (Browser, Vision, Filesystem)
│   ├── cli/                 #    - [终端] DX 调试套件 (config, doctor, logs, new)
│   ├── bus/                 #    - [总线] 消息分发与命令队列 (CommandQueue)
│   ├── channels/            #    - [渠道] 统一消息网关 (Telegram, Feishu)
│   ├── utils/               #    - [工具] 审计 (Audit)、路径助手等
│   └── providers/           #    - [适配] 多模型统一调用工厂
│
├── .home/                   # 📄 数据目录 (start.sh 默认)
│   ├── gateway.log          #    - 网关运行日志
│   └── audit.log            #    - 审计日志
├── workspace/               # 📂 活跃工作区 (灵魂、指令与主动性)
│   ├── IDENTITY.md          #    - [核心] 身份与使命
│   ├── SOUL.md              #    - [性格] 语气、价值观、性格标签
│   ├── AGENTS.md            #    - [协议] 技术硬协议与委派逻辑
│   ├── TOOLS.md             #    - [手册] 工具操作秘籍 (Recipes)
│   ├── HEARTBEAT.md         #    - [主动] 秘书日常维护任务
│   ├── skills/              #    - [能力] 外挂专家技能库
│   └── memory/              #    - [记忆] 经整理的长短期知识库
│
├── docs/                    # 📄 深度文档
│   ├── CONFIG_GUIDE_CN.md   #    - 高级配置指南 (推荐先看)
│   └── PROJECT_STRUCTURE.md #    - 本文件
│
├── README.md                # 📘 项目主入口
└── pyproject.toml           # ⚙️ 依赖与工具链配置
```

---

## 🔑 核心组件说明

| 组件 | 作用 | 修改场景 |
| :--- | :--- | :--- |
| **`nanobot/agent/loop.py`** | 系统的 CPU。 | 修改思考逻辑或错误重试机制。 |
| **`workspace/AGENTS.md`** | 系统的 执行协议。 | 改变委派规则、搜索流程或失败处理。 |
| **`workspace/HEARTBEAT.md`**| 系统的 生物钟。 | 增加定期的“秘书”自动巡检任务。 |
| **`nanobot cli`** | 系统的 诊断工具箱。 | 使用 `nanobot doctor` 排查环境问题。 |

---
*注：本项目已将默认工作区设为 ./workspace，所有提示词修改将实时生效。🐾*
