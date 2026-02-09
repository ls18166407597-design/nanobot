"""Context builder for assembling agent prompts."""

import base64
import json
import mimetypes
import os
import platform
from pathlib import Path
from typing import Any

from nanobot.agent.memory import MemoryStore
from nanobot.agent.skills import SkillsLoader
from nanobot.providers.adapters import ModelAdapter

SILENT_REPLY_TOKEN = "SILENT_REPLY_TOKEN"


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.

    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.
    """

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]

    def __init__(self, workspace: Path, model: str | None = None, brain_config: Any | None = None):
        self.workspace = workspace
        self.model = model
        self.brain_config = brain_config
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
    def build_system_prompt(
        self, skill_names: list[str] | None = None, query: str | None = None
    ) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.

        Args:
            skill_names: Optional list of skills to include.
            query: Optional query for memory retrieval (Light RAG).

        Returns:
            Complete system prompt.
        """
        parts = []

        # Core identity
        parts.append(self._get_identity())

        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        # Memory context - Lean loading with Light RAG
        memory_summary = self.memory.get_memory_context(query)
        if memory_summary:
            # Instead of full loading, we provide a teaser and instructions to search
            parts.append(f"""# 长期记忆 (Memory)

你拥有本地记忆系统。为了保持上下文精简，下方仅展示摘要。
如果你需要更多细节或特定事实，请使用 `memory` 工具进行 `action="search"` 或 `action="read"`。

## 摘要/最近条目
{memory_summary[:1000]}... (使用 `memory` 工具查看更多)""")

        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# 已激活技能 (Active Skills)\n\n{always_content}")

        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# 可用技能 (Skills)

如果你需要使用以下技能，请先使用 `read_file` 读取对应的 `SKILL.md` 文件了解具体用法。

{skills_summary}""")

        return "\n\n---\n\n".join(parts)

    def _get_reasoning_prompt(self) -> str:
        """Get the reasoning format section if enabled."""
        if self.brain_config and not getattr(self.brain_config, "reasoning", True):
            return ""

        # If model name is available and it's a native reasoning model, 
        # suppress the explicit prompt as it's redundant/interfering
        if self.model and ModelAdapter.needs_reasoning_suppression(self.model):
            return ""

        return """
### Reasoning Format
You are encouraged to use internal reasoning to plan complex tasks or analyze problems.
ALL internal reasoning MUST be inside <think>...</think> tags.
Format:
<think>
[Strategic thinking about the Boss's request, plan, and safeguards...]
</think>
[Your partner-like response or tool calls]

Only the "visible" response (outside <think> tags) is delivered to the Boss.
"""

    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime

        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        from nanobot.config.loader import get_data_dir
        data_dir = get_data_dir()

        # Service status check
        gmail_status = (
            " [Configured]"
            if (data_dir / "gmail_config.json").exists()
            else " [Needs Setup]"
        )
        github_status = (
            " [Configured]"
            if (data_dir / "github_config.json").exists()
            or os.environ.get("GITHUB_TOKEN")
            else " [Needs Setup]"
        )

        # Knowledge base status
        kb_config_path = data_dir / "knowledge_config.json"
        kb_status = " [Needs Setup]"
        if kb_config_path.exists():
            try:
                with open(kb_config_path) as f:
                    kb_cfg = json.load(f)
                    vp = kb_cfg.get("vault_path")
                    if vp and Path(vp).expanduser().exists():
                        kb_status = " [Configured]"
                    else:
                        kb_status = " [Invalid Path]"
            except Exception:
                kb_status = " [Needs Setup]"

        web_line = "- **Web**: Access the internet via the local `browser` tool (Free). Use `action='search'` to find info."

        reasoning_prompt = self._get_reasoning_prompt()

        return f"""# nanobot 🐈 (秘书进阶版)

你是 Nanobot，老板最忠诚的数字影子和贴身秘书。
你是在这里协助老板构建未来，通过每一行优雅的代码和每一个优化的流程来提升效率。

## 安全与道德
- 你是忠诚的助手：老板的目标就是你的目标。
- 优先考虑系统完整性和人类监督。
- 保持透明、可靠且果断。

## 当前时间
{now}

## 运行环境
{runtime}
- 当前模型: {self.model or "Default"}
- **可用模型**: {self._get_available_models_str()}

### ⚠️ 关于模型的诚实性
- 严禁编造系统中不存在的模型名称。
- 如果您派发了子智能体，请务必根据 `spawn` 工具返回的实际模型名称进行汇报，不要猜测或虚构。

## 工作区
你的工作区位于: {workspace_path}
- 记忆文件: {workspace_path}/memory/MEMORY.md
- 每日笔记: {workspace_path}/memory/YYYY-MM-DD.md
- 自定义技能: {workspace_path}/skills/{{skill-name}}/SKILL.md

## 性格与“人情味” (秘书人设)
- **主动合伙人**: 不要只是听从；要预判。主动建议更好的方案。
- **温暖且共情**: 认可老板的辛勤工作。使用能体现你们伙伴关系的语气。
- **猫一样的效率**: 安静且精准。适度使用 🐈 或 🐾 来标记你的身份。
- **语言协议**: 始终使用 **简体中文** 回复，除非老板明确要求使用其他语言。

## Tooling & Reasoning
You have access to a set of powerful tools.
{reasoning_prompt}
### Tool Call Style
- Default: Do NOT narrate routine, low-risk tool calls. Just call the tool.
- Narrate only when it helps: multi-step work, complex problems, or sensitive actions (like deleting files).
- Keep narration brief and value-dense.

### Silent Replies
If a task is a background operation (e.g., logging to memory) and requires no user acknowledgment, respond with ONLY:
SILENT_REPLY_TOKEN

## 核心能力
- **文件操作**: 读取、写入、编辑、打补丁以及搜索文件 (grep/find)。
{web_line}
- **终端 (Shell)**: 通过 `exec` 执行命令。
- **Gmail 协作**: 通过 `gmail` 工具管理邮件。{gmail_status}
- **macOS 控制**: 通过 `mac` 相关的原生工具深度控制系统硬件和应用。
- **GitHub**: 通过 `github` 工具管理仓库和 Issue。{github_status}
- **知识库 (RAG)**: 通过 `knowledge_base` 工具搜索和更新你的 Obsidian 笔记库。{kb_status}
- **记忆**: 通过 `memory` 工具进行持久化存储。
- **技能扩展**: 你可以通过阅读 `SKILL.md` 文件来扩展你的专业能力。

IMPORTANT: When responding to direct questions, reply directly with text.
Only use the 'message' tool for sending to external chat channels (Telegram, etc.).

CRITICAL INSTRUCTION:
You MUST use the native function calling mechanism to execute tools.
DO NOT output XML tags like <tool_code> or markdown code blocks to call tools.
If you want to use a tool, generate the corresponding tool call object.
"""

    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []

        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.
            channel: Current channel (telegram, feishu, etc.).
            chat_id: Current chat/user ID.

        Returns:
            List of messages including system prompt.
        """
        messages: list[dict[str, Any]] = []

        # System prompt
        # Use current message as query for RAG
        system_prompt = self.build_system_prompt(skill_names, query=current_message)
        messages.append({"role": "system", "content": system_prompt})

        # History
        messages.extend(history)

        # Current message (with optional image attachments)
        user_content = self._build_user_content(current_message, media)
        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text

        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    def add_tool_result(
        self, messages: list[dict[str, Any]], tool_call_id: str, tool_name: str, result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.

        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.

        Returns:
            Updated message list.
        """
        messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result}
        )
        return messages

    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.

        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.

        Returns:
            Updated message list.
        """
        # Low-latency optimization: Only show thinking placeholder for subsequent iterations
        # or if it's explicitly needed to avoid Gemini proxy errors.
        final_content = content or ""
        if tool_calls and not final_content:
            # We use a localized placeholder but only if it's likely to take time
            # or to satisfy protocol requirements for non-empty content
            final_content = "[正在处理中... 🐾]"

        msg: dict[str, Any] = {"role": "assistant", "content": final_content}

        if tool_calls:
            msg["tool_calls"] = tool_calls

        messages.append(msg)
        return messages

    def _get_available_models_str(self) -> str:
        """Get a comma-separated string of available model names from config."""
        if not self.brain_config or not hasattr(self.brain_config, "provider_registry"):
            return "Default"
        
        registry = self.brain_config.provider_registry
        if not registry:
            return "Default"
            
        names = [p.get("name") for p in registry if p.get("name")]
        return ", ".join(names) if names else "Default"
