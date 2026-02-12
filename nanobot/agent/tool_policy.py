"""Tool exposure policy per turn to reduce overlapping tool choices."""

from __future__ import annotations

import re
from typing import Any


class ToolPolicy:
    """Decide which tools should be exposed to the model in current iteration."""

    WEB_TOOLS = {"tavily", "browser", "mcp"}
    VALID_WEB_DEFAULT = {"tavily", "browser"}

    def __init__(
        self,
        *,
        web_default: str = "tavily",
        enable_mcp_fallback: bool = True,
        allow_explicit_mcp: bool = True,
    ):
        self.web_default = web_default if web_default in self.VALID_WEB_DEFAULT else "tavily"
        self.enable_mcp_fallback = bool(enable_mcp_fallback)
        self.allow_explicit_mcp = bool(allow_explicit_mcp)

    def filter_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tool_definitions: list[dict[str, Any]],
        failed_tools: set[str],
    ) -> list[dict[str, Any]]:
        if not tool_definitions:
            return tool_definitions

        latest_user = self._latest_user_text(messages).lower()
        explicit_mcp = self._wants_mcp(latest_user)
        browser_needed = self._needs_browser(latest_user)

        web_present = {self._tool_name(td) for td in tool_definitions if self._tool_name(td) in self.WEB_TOOLS}
        if not web_present:
            return tool_definitions

        preferred = "browser" if browser_needed else self.web_default
        if preferred in failed_tools:
            preferred = "browser" if preferred == "tavily" else "tavily"

        allow_web: set[str] = set()
        if preferred in web_present:
            allow_web.add(preferred)

        both_core_failed = "tavily" in failed_tools and "browser" in failed_tools
        can_use_mcp = (self.allow_explicit_mcp and explicit_mcp) or (
            self.enable_mcp_fallback and both_core_failed
        )
        if can_use_mcp:
            if "mcp" in web_present:
                allow_web.add("mcp")

        # If the chosen preferred tool is unavailable, keep available core options.
        if not allow_web:
            for n in ("tavily", "browser"):
                if n in web_present:
                    allow_web.add(n)
            if "mcp" in web_present and self.allow_explicit_mcp and explicit_mcp:
                allow_web.add("mcp")

        filtered: list[dict[str, Any]] = []
        for td in tool_definitions:
            name = self._tool_name(td)
            if name in self.WEB_TOOLS and name not in allow_web:
                continue
            filtered.append(td)
        return filtered

    def _tool_name(self, tool_def: dict[str, Any]) -> str:
        fn = tool_def.get("function", {})
        return str(fn.get("name", ""))

    def _latest_user_text(self, messages: list[dict[str, Any]]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, str):
                    return content
        return ""

    def _wants_mcp(self, text: str) -> bool:
        return bool(re.search(r"mcp|model context protocol|playwright mcp|github mcp", text))

    def _needs_browser(self, text: str) -> bool:
        keywords = (
            "网页",
            "页面",
            "渲染",
            "点击",
            "登录",
            "交互",
            "dom",
            "浏览器",
            "打开网站",
            "browser",
            "browse",
        )
        return any(k in text for k in keywords)
