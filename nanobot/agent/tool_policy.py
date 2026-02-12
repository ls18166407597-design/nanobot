"""Tool exposure policy per turn to reduce overlapping tool choices."""

from __future__ import annotations

import json
import re
from typing import Any

from nanobot.utils.helpers import get_tool_config_path


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
        intent_rules: list[dict[str, Any]] | None = None,
        tool_capabilities: dict[str, list[str]] | None = None,
    ):
        self.web_default = web_default if web_default in self.VALID_WEB_DEFAULT else "tavily"
        self.enable_mcp_fallback = bool(enable_mcp_fallback)
        self.allow_explicit_mcp = bool(allow_explicit_mcp)
        self.intent_rules = intent_rules or [
            {"capability": "code_hosting", "keywords": ["github", "issue", "pr", "repo", "commit"]},
            {"capability": "train_ticket", "keywords": ["火车票", "12306", "车次", "余票", "高铁", "动车"]},
            {"capability": "weather", "keywords": ["天气", "气温", "降雨", "湿度", "风力", "空气质量", "aqi"]},
        ]
        self.tool_capabilities = tool_capabilities or {
            "github": ["code_hosting", "issue_tracking"],
            "weather": ["weather"],
            "gmail": ["email"],
            "qq_mail": ["email"],
            "tianapi": ["news"],
            "tushare": ["finance"],
        }

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
        target_capability = self._match_intent_capability(latest_user)

        if target_capability:
            preferred = self._pick_specialized_tool(tool_definitions, target_capability)
            if preferred and preferred not in failed_tools:
                return self._keep_tool_with_non_web(tool_definitions, keep_tool=preferred, explicit_mcp=explicit_mcp)
            return self._filter_web_tools(
                tool_definitions=tool_definitions,
                failed_tools=failed_tools,
                explicit_mcp=explicit_mcp,
                browser_needed=browser_needed,
            )

        return self._filter_web_tools(
            tool_definitions=tool_definitions,
            failed_tools=failed_tools,
            explicit_mcp=explicit_mcp,
            browser_needed=browser_needed,
        )

    def _filter_web_tools(
        self,
        *,
        tool_definitions: list[dict[str, Any]],
        failed_tools: set[str],
        explicit_mcp: bool,
        browser_needed: bool,
    ) -> list[dict[str, Any]]:
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
        if can_use_mcp and "mcp" in web_present:
            allow_web.add("mcp")

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

    def _pick_specialized_tool(
        self,
        tool_definitions: list[dict[str, Any]],
        capability: str,
    ) -> str | None:
        available = {self._tool_name(td) for td in tool_definitions}

        # 1) dedicated tools with declared capability
        for name, caps in self.tool_capabilities.items():
            if name in available and capability in set(caps):
                return name

        # 2) mcp server declares capability in mcp_config.json -> route to generic mcp tool
        if "mcp" in available and self._mcp_supports_capability(capability):
            return "mcp"

        # 3) fallback for common MCP-first domains when mcp tool is available.
        if "mcp" in available and capability in {"train_ticket", "maps", "flight_ticket"}:
            return "mcp"

        return None

    def _mcp_supports_capability(self, capability: str) -> bool:
        cfg_path = get_tool_config_path("mcp_config.json")
        if not cfg_path.exists():
            return False
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return False
        servers = cfg.get("servers", {})
        if not isinstance(servers, dict):
            return False
        for name, server in servers.items():
            if not isinstance(server, dict) or not bool(server.get("enabled", True)):
                continue
            caps = server.get("capabilities")
            if isinstance(caps, list) and capability in {str(c) for c in caps}:
                return True
            # fallback heuristic for existing configs without capabilities
            lowered = str(name).lower()
            if capability == "train_ticket" and ("12306" in lowered or "train" in lowered):
                return True
            if capability == "code_hosting" and "github" in lowered:
                return True
        return False

    def _keep_tool_with_non_web(
        self,
        tool_definitions: list[dict[str, Any]],
        *,
        keep_tool: str,
        explicit_mcp: bool,
    ) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        for td in tool_definitions:
            name = self._tool_name(td)
            if name == keep_tool:
                filtered.append(td)
                continue
            if name in self.WEB_TOOLS:
                continue
            filtered.append(td)
        if explicit_mcp and keep_tool != "mcp":
            for td in tool_definitions:
                if self._tool_name(td) == "mcp" and td not in filtered:
                    filtered.append(td)
                    break
        return filtered

    def _match_intent_capability(self, text: str) -> str | None:
        for rule in self.intent_rules:
            if not isinstance(rule, dict):
                continue
            cap = str(rule.get("capability", "")).strip()
            keywords = rule.get("keywords", [])
            if not cap or not isinstance(keywords, list):
                continue
            if any(str(k).lower() in text for k in keywords):
                return cap
        return None

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
