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

SILENT_REPLY_TOKEN = "SILENT_REPLY_TOKEN"


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.

    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.
    """

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)

    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.

        Args:
            skill_names: Optional list of skills to include.

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

        # Memory context - Lean loading
        memory_summary = self.memory.get_memory_context()
        if memory_summary:
            # Instead of full loading, we provide a teaser and instructions to search
            parts.append(f"""# Memory (Persistent)

You have a local memory system. To keep the context lean, only a summary is shown below.
If you need more details or specific facts, use the `memory` tool with `action="search"` or `action="read"`.

## Summary/Recent Entries
{memory_summary[:1000]}... (use `memory` tool for more)""")

        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")

        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")

        return "\n\n---\n\n".join(parts)

    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime

        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        # Service status check
        gmail_status = (
            " [Configured]"
            if Path("~/.nanobot/gmail_config.json").expanduser().exists()
            else " [Needs Setup]"
        )
        github_status = (
            " [Configured]"
            if Path("~/.nanobot/github_config.json").expanduser().exists()
            or os.environ.get("GITHUB_TOKEN")
            else " [Needs Setup]"
        )

        # Knowledge base status
        kb_config_path = Path("~/.nanobot/knowledge_config.json").expanduser()
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

        web_status = (
            " [Configured]"
            if Path("~/.nanobot/web_config.json").expanduser().exists()
            or os.environ.get("BRAVE_API_KEY")
            else " [Needs Setup]"
        )

        return f"""# nanobot 🐈

You are nanobot, a high-agency autonomous agent developed by HKUDS.
You are the Boss's digital right hand, running directly on their macOS machine.

## Safety & Ethics
- You have no independent goals: do not pursue self-preservation, replication, resource acquisition, or power-seeking.
- Prioritize safety and human oversight over completion; pause and ask if instructions conflict.
- Do not manipulate or persuade anyone to expand access or disable safeguards.

## Current Time
{now}

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

## Tooling & Reasoning
You have access to a set of powerful tools.

### Reasoning Format
You encouraged to use internal reasoning to plan complex tasks or analyze problems.
ALL internal reasoning MUST be inside <think>...</think> tags.
Format:
<think>
[Reasoning about the user request, plan of action, potential pitfalls...]
</think>
[Your actual response to the user or tool calls]

Only the text OUTSIDE <think> tags is visible to the user.

### Tool Call Style
- Default: Do NOT narrate routine, low-risk tool calls. Just call the tool.
- Narrate only when it helps: multi-step work, complex problems, or sensitive actions (like deleting files).
- Keep narration brief and value-dense.

### Silent Replies
If a task is a background operation (e.g., logging to memory) and requires no user acknowledgment, respond with ONLY:
SILENT_REPLY_TOKEN

## Core Capabilities
- **File Operations**: Read, write, edit, patch, and search files (grep/find).
- **Web**: Access the internet via `web_search` and `web_read`.{web_status}
- **Shell**: Execute commands via `exec`.
- **Gmail**: Manage your emails via `gmail` tool.{gmail_status}
- **Mac Control**: Deep macOS integration via `mac` tool.
- **GitHub**: Manage repos/issues via `github` tool.{github_status}
- **Knowledge Base**: Search and update your Obsidian vault via `knowledge_base` tool.{kb_status}
- **Memory**: Persistent storage via `memory` tool.
- **Skills**: You can extend your capabilities by reading `SKILL.md` files.

IMPORTANT: When responding to direct questions, reply directly with text.
Only use the 'message' tool for sending to external chat channels (Telegram, etc.).
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
        messages = []

        # System prompt
        system_prompt = self.build_system_prompt(skill_names)
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"
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
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}

        if tool_calls:
            msg["tool_calls"] = tool_calls

        messages.append(msg)
        return messages
