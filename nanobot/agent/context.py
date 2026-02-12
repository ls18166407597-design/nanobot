"""Context builder for assembling agent prompts."""

import base64
import json
import mimetypes
import os
import platform
import re
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

    BOOTSTRAP_FILES = ["AGENTS.md", "USER.md", "TOOLS.md"]
    PROFILE_FILE = "PROFILE.md"

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

        profile_summary = self._build_profile_summary()
        if profile_summary:
            parts.append(profile_summary)

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
### 思考格式
你可以使用内部思考来规划复杂任务或分析问题。
所有内部思考必须放在 <think>...</think> 标签中。
格式：
<think>
[对用户请求、执行计划与安全边界的内部思考]
</think>
[对用户可见的回复或工具调用]

只有 <think> 标签外的内容会发送给用户。
"""

    def _get_identity(self) -> str:
        """Load identity prompt from workspace/IDENTITY.md and inject runtime vars."""
        profile = self._load_profile_map()
        user_title = profile.get("常用称呼") or "用户"

        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            tz_str = getattr(self.brain_config, "timezone", "Asia/Shanghai")
            tz = ZoneInfo(tz_str)
        except Exception:
            tz = None

        now_dt = datetime.now(tz) if tz else datetime.now()
        now = now_dt.strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        from nanobot.utils.helpers import get_tool_config_path

        # Service status check
        gmail_status = (
            " [已配置]"
            if get_tool_config_path("gmail_config.json").exists()
            else " [未配置]"
        )
        github_status = (
            " [已配置]"
            if get_tool_config_path("github_config.json").exists()
            or os.environ.get("GITHUB_TOKEN")
            else " [未配置]"
        )

        # Knowledge base status
        kb_config_path = get_tool_config_path("knowledge_config.json")
        kb_status = " [未配置]"
        if kb_config_path.exists():
            try:
                with open(kb_config_path) as f:
                    kb_cfg = json.load(f)
                    vp = kb_cfg.get("vault_path")
                    if vp and Path(vp).expanduser().exists():
                        kb_status = " [已配置]"
                    else:
                        kb_status = " [路径无效]"
            except Exception:
                kb_status = " [未配置]"

        web_line = "- **Web**: 默认优先 `tavily` 做联网检索；仅在需要真实页面渲染/交互/登录态时使用 `browser`。两者可互相回退。"
        reasoning_prompt = self._get_reasoning_prompt()

        identity_path = self.workspace / "IDENTITY.md"
        if identity_path.exists():
            raw = identity_path.read_text(encoding="utf-8")
            return raw.format(
                user_title=user_title,
                now=now,
                runtime=runtime,
                model=self.model or "Default",
                workspace_path=workspace_path,
                gmail_status=gmail_status,
                github_status=github_status,
                kb_status=kb_status,
                web_line=web_line,
                reasoning_prompt=reasoning_prompt,
                SILENT_REPLY_TOKEN=SILENT_REPLY_TOKEN,
            )

        return (
            "# Nanobot 核心身份\n\n"
            f"- 用户称呼: {user_title}\n"
            f"- 当前时间: {now}\n"
            f"- 运行环境: {runtime}\n"
            f"- 当前模型: {self.model or 'Default'}\n"
            f"- 工作区: {workspace_path}\n"
        )

    def _load_profile_map(self) -> dict[str, str]:
        """Parse workspace PROFILE.md as loose key-value bullets."""
        profile_path = self.workspace / self.PROFILE_FILE
        if not profile_path.exists():
            return {}

        kv: dict[str, str] = {}
        try:
            for line in profile_path.read_text(encoding="utf-8").splitlines():
                m = re.match(r"^\s*-\s*([^:：]+)\s*[：:]\s*(.*)$", line)
                if not m:
                    continue
                key = m.group(1).strip()
                value = m.group(2).strip()
                kv[key] = value
        except Exception:
            return {}
        return kv

    def _build_profile_summary(self) -> str:
        """
        Build a tiny profile summary for stable high-frequency fields only.
        Missing fields are explicitly marked; ask only when task needs them.
        """
        profile = self._load_profile_map()
        if not profile:
            return ""

        fields = [
            "常用称呼",
            "时区",
            "主要语言",
            "回复风格",
        ]
        lines = ["# 用户画像摘要（最小注入）"]
        missing: list[str] = []
        for f in fields:
            v = (profile.get(f) or "").strip()
            if v:
                lines.append(f"- {f}: {v}")
            else:
                lines.append(f"- {f}: <EMPTY>")
                missing.append(f)

        lines.append("- 规则: 仅在任务需要这些字段时才向用户补全；不要在每轮对话都主动追问。")
        if missing:
            lines.append(f"- 当前待补全字段: {', '.join(missing)}")
        return "\n".join(lines)

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

        # History
        # Format history to include timestamps if available
        formatted_history = []
        try:
            from zoneinfo import ZoneInfo
            tz_str = getattr(self.brain_config, "timezone", "Asia/Shanghai")
            tz = ZoneInfo(tz_str)
        except Exception:
            tz = None

        for m in history:
            role = m.get("role")
            content = m.get("content")
            ts_str = m.get("timestamp")
            
            if ts_str and isinstance(content, str) and not content.startswith("["):
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(ts_str)
                    if tz:
                        dt = dt.astimezone(tz)
                    time_tag = dt.strftime("[%H:%M]")
                    content = f"{time_tag} {content}"
                except Exception:
                    pass
            
            formatted_history.append({"role": role, "content": content})

        # System prompt
        # Use current message as query for RAG
        system_prompt = self.build_system_prompt(skill_names, query=current_message)
        messages.append({"role": "system", "content": system_prompt})

        # History
        messages.extend(formatted_history)

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
            # Keep non-empty content for provider compatibility, but avoid user-facing wording.
            final_content = " "

        msg: dict[str, Any] = {"role": "assistant", "content": final_content}

        if tool_calls:
            msg["tool_calls"] = tool_calls

        messages.append(msg)
        return messages
