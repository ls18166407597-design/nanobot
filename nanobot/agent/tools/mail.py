"""Unified mail tool routing to gmail/qq_mail tools."""

from __future__ import annotations

from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult


class MailTool(Tool):
    """Unified email entrypoint for agent."""

    name = "mail"
    description = (
        "统一邮件入口工具。自动或按 provider 路由到 gmail/qq_mail。"
        "支持 action: setup/list/read/send/status。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["setup", "list", "read", "send", "status"],
            },
            "provider": {
                "type": "string",
                "enum": ["auto", "gmail", "qq_mail"],
                "description": "默认 auto（优先 gmail，其次 qq_mail）",
            },
            "limit": {"type": "integer"},
            "email_id": {"type": "string"},
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "setup_email": {"type": "string"},
            "setup_password": {"type": "string"},
        },
        "required": ["action"],
    }

    def __init__(self, tools: Any):
        self._tools = tools

    async def execute(
        self,
        action: str,
        provider: str = "auto",
        **kwargs: Any,
    ) -> ToolResult:
        target_name = self._pick_provider(provider)
        if not target_name:
            return ToolResult(
                success=False,
                output="Error: 未找到可用邮件工具（gmail/qq_mail）。",
                remedy="请启用并配置 gmail 或 qq_mail 工具。",
            )

        target = self._tools.get(target_name)
        if target is None:
            return ToolResult(
                success=False,
                output=f"Error: 目标邮件工具不可用: {target_name}",
                remedy="请检查 enabled_tools 配置。",
            )

        res = await target.execute(action=action, **kwargs)
        if isinstance(res, ToolResult):
            return res
        return ToolResult(success=True, output=str(res))

    def _pick_provider(self, provider: str) -> str | None:
        p = (provider or "auto").strip()
        if p in {"gmail", "qq_mail"}:
            return p

        # auto route: prefer gmail then qq_mail
        if self._tools.get("gmail") is not None:
            return "gmail"
        if self._tools.get("qq_mail") is not None:
            return "qq_mail"
        return None
