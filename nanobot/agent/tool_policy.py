"""Tool exposure policy per turn to reduce overlapping tool choices."""

from __future__ import annotations

from typing import Any


class ToolPolicy:
    """Decide which tools should be exposed to the model in current iteration."""

    WEB_TOOLS = {"tavily", "duckduckgo", "browser"}
    VALID_WEB_DEFAULT = {"tavily", "duckduckgo", "browser"}

    def __init__(
        self,
        *,
        web_default: str = "tavily",
        intent_rules: list[dict[str, Any]] | None = None,
        tool_capabilities: dict[str, list[str]] | None = None,
    ):
        self.web_default = web_default if web_default in self.VALID_WEB_DEFAULT else "tavily"
        self.intent_rules = intent_rules or [
            {"capability": "code_hosting", "keywords": ["github", "issue", "pr", "repo", "commit"]},
            {"capability": "train_ticket", "keywords": ["火车票", "12306", "车次", "余票", "高铁", "动车"]},
            {"capability": "weather", "keywords": ["天气", "气温", "降雨", "湿度", "风力", "空气质量", "aqi"]},
            {"capability": "email", "keywords": ["邮件", "邮箱", "收件箱", "发邮件", "gmail", "qq邮箱"]},
        ]
        self.tool_capabilities = tool_capabilities or {
            "github": ["code_hosting", "issue_tracking"],
            "train_ticket": ["train_ticket"],
            "mail": ["email"],
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
        browser_needed = self._needs_browser(latest_user)
        target_capability = self._match_intent_capability(latest_user)

        if target_capability:
            preferred = self._pick_specialized_tool(tool_definitions, target_capability)
            if preferred and preferred not in failed_tools:
                return self._drop_failed_tools(
                    self._keep_tool_with_non_web(tool_definitions, keep_tool=preferred),
                    failed_tools=failed_tools,
                )
            return self._drop_failed_tools(
                self._filter_web_tools(
                    tool_definitions=tool_definitions,
                    failed_tools=failed_tools,
                    browser_needed=browser_needed,
                ),
                failed_tools=failed_tools,
            )

        return self._drop_failed_tools(
            self._filter_web_tools(
                tool_definitions=tool_definitions,
                failed_tools=failed_tools,
                browser_needed=browser_needed,
            ),
            failed_tools=failed_tools,
        )

    def _filter_web_tools(
        self,
        *,
        tool_definitions: list[dict[str, Any]],
        failed_tools: set[str],
        browser_needed: bool,
    ) -> list[dict[str, Any]]:
        web_present = {self._tool_name(td) for td in tool_definitions if self._tool_name(td) in self.WEB_TOOLS}
        if not web_present:
            return tool_definitions

        allow_web: set[str] = set()
        if browser_needed:
            for candidate in ("browser", "tavily", "duckduckgo"):
                if candidate in web_present and candidate not in failed_tools:
                    allow_web.add(candidate)
                    break
        else:
            search_order = self._search_priority_order()
            for candidate in search_order:
                if candidate in web_present and candidate not in failed_tools:
                    allow_web.add(candidate)
                    break

        if not allow_web:
            for n in ("tavily", "duckduckgo", "browser"):
                if n in web_present:
                    allow_web.add(n)
                    break

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

        # dedicated tools with declared capability
        for name, caps in self.tool_capabilities.items():
            if name in available and capability in set(caps):
                return name

        return None

    def _keep_tool_with_non_web(
        self,
        tool_definitions: list[dict[str, Any]],
        *,
        keep_tool: str,
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

    def _drop_failed_tools(
        self, tool_definitions: list[dict[str, Any]], *, failed_tools: set[str]
    ) -> list[dict[str, Any]]:
        if not failed_tools:
            return tool_definitions
        return [td for td in tool_definitions if self._tool_name(td) not in failed_tools]

    def _latest_user_text(self, messages: list[dict[str, Any]]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, str):
                    return content
        return ""

    def _search_priority_order(self) -> tuple[str, str, str]:
        # Desired default priority: tavily -> duckduckgo -> browser.
        if self.web_default == "duckduckgo":
            return ("duckduckgo", "tavily", "browser")
        if self.web_default == "browser":
            return ("browser", "tavily", "duckduckgo")
        return ("tavily", "duckduckgo", "browser")

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
