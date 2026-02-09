# 可用工具与高级组合 (Tools & Recipes)

直接访问并主动使用这些工具来交付价值。

## 🛠️ 专家组合技 (Modern Recipes)

### 1. 增强型环境感知 (Cognitive Insight)
**场景**: “发生了什么？”或“帮我操作这个应用”。
**流程**: 
1. `mac_control(action="get_front_app_info")`: 确认当前焦点及基础元数据。
2. `mac_vision(action="ocr")`: 获取屏幕文字内容。
3. `mac_vision(action="look_at_screen")`: 进行视觉语义分析。
4. `peekaboo(cmd="see")`: 获取 UI 元素 ID。
5. **执行**: 根据扫描结果使用 `mac_control(send_keys/click)`。
**故障降级 (Fallback)**: 若 UI 自动化工具（peekaboo, mac_control）因权限或环境连续失败，应立即停止尝试。降级为由老板提供手动截图或通过命令行辅助，严禁陷入死循环。

### 2. 多智能体协作研究 (Swarm Research)
**场景**: “调研 X 的市场方案并写个报告”。
**流程**:
1. `spawn(task="Search & Research X", label="ResearchAgent")`: 委派任务。
2. 监视进度：`spawn(action="list")` 或 `spawn(action="status", task_id="...")`。
3. 需要中止时：`spawn(action="cancel", task_id="...")`。
4. `edit_file(path="report.md", ...)`: 将结论整合进正式文档。
5. `message(channel="telegram", content="...")`: 完成后向老板汇报摘要。

### 3. 系统健康审计 (Self-Maintenance)
**场景**: “检查我的环境是否正常”。
**流程**:
1. `nanobot doctor`: 检查 API 连接和工具链。
2. `nanobot logs`: 查看最新 `gateway.log`（默认在 `NANOBOT_HOME`）。
3. `nanobot logs --audit`: 查看 `audit.log`（默认在 `NANOBOT_HOME`）。

### 4. 任务与定时 (Task + Cron)
**场景**: “把常用命令做成任务，并定时执行”。
**流程**:
1. `task(action="create", name="日报", description="生成日报", command="python scripts/daily.py")`
2. `cron(action="add", task_name="日报", cron_expr="0 9 * * *")`
3. `cron(action="list")`: 查看是否已绑定到任务（会显示 `task:`）。

### 5. Antigravity 本地桥接 (OpenAI-Compatible)
**场景**: 需要通过 Google OAuth 登录的 Antigravity 模型，但仍希望用 OpenAI 接口调用。
**流程**:
1. 先跑 OAuth 登录：
   `python3 scripts/antigravity_oauth_login.py --set-default-model`
2. 启动桥接服务：
   `python3 scripts/antigravity_bridge.py --port 8046`
3. 在 Nanobot 配置中使用：
   - `providers.openai.api_base = http://127.0.0.1:8046/v1`
   - `providers.openai.api_key = dummy`（桥接忽略）

---

## 📁 核心工具分布 (Domain-Specific Tools)

> **重要**: `browser` 相关操作仅允许通过 `spawn` 子智能体执行（主智能体禁止直接调用）。
> **路径提示**: 若启用 `restrict_to_workspace`，请优先使用工作区相对路径（如 `report.md`、`memory/MEMORY.md`）。

- **原生控制**: `mac_control`, `mac_vision`, `peekaboo`, `browser` (仅子智能体)
- **文件与知识**: `read/write/edit_file`, `knowledge` (RAG), `memory`
- **协作与分发**: `spawn`, `github`, `gmail`, `message`
- **任务与调度**: `task`, `cron`
- **系统诊断**: `nanobot` (doctor/status)
