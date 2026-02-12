"""DuckDuckGo search tool backed by MCP server."""

from __future__ import annotations

import json
from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.mcp import MCPServerConfig, MCPStdioClient
from nanobot.utils.helpers import get_tool_config_path


class DuckDuckGoTool(Tool):
    """Search web information via duckduckgo MCP server."""

    name = "duckduckgo"
    description = "使用 DuckDuckGo 执行网页信息检索（MCP 后端）。适合通用信息查询。"
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["search"]},
            "query": {"type": "string", "description": "搜索关键词"},
            "count": {"type": "integer", "minimum": 1, "maximum": 20, "description": "返回结果数量"},
            "safe_search": {
                "type": "string",
                "enum": ["strict", "moderate", "off"],
                "description": "安全搜索级别",
            },
            "timeout": {"type": "integer", "minimum": 1, "maximum": 120},
        },
        "required": ["action", "query"],
    }

    async def execute(
        self,
        action: str,
        query: str,
        count: int = 10,
        safe_search: str = "moderate",
        timeout: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        if action != "search":
            return ToolResult(success=False, output=f"Error: unsupported action '{action}'.")

        cfg, err = self._build_server_config(timeout=timeout)
        if err:
            return ToolResult(success=False, output=err)

        args = {
            "query": query,
            "count": max(1, min(20, int(count or 10))),
            "safeSearch": safe_search if safe_search in {"strict", "moderate", "off"} else "moderate",
        }
        try:
            async with MCPStdioClient(cfg) as client:
                await client.initialize()
                result = await client.request("tools/call", {"name": "duckduckgo_web_search", "arguments": args})
        except Exception as e:
            return ToolResult(success=False, output=f"Error querying duckduckgo: {e}")

        output = self._render_result(result)
        return ToolResult(success=not bool(result.get("isError", False)), output=output)

    def _build_server_config(self, timeout: int | None) -> tuple[MCPServerConfig | None, str | None]:
        path = get_tool_config_path("mcp_config.json")
        if not path.exists():
            return None, "Error: mcp_config.json not found."
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            return None, f"Error: failed to parse mcp_config.json: {e}"

        raw = (cfg.get("servers") or {}).get("duckduckgo")
        if not isinstance(raw, dict):
            return None, "Error: MCP server 'duckduckgo' not found in mcp_config.json."
        if not bool(raw.get("enabled", True)):
            return None, "Error: MCP server 'duckduckgo' is disabled."
        command = str(raw.get("command", "")).strip()
        if not command:
            return None, "Error: MCP server 'duckduckgo' command is empty."

        request_timeout = int(raw.get("request_timeout", 20))
        if timeout is not None:
            request_timeout = max(1, min(120, int(timeout)))

        return (
            MCPServerConfig(
                command=command,
                args=[str(x) for x in (raw.get("args") or [])],
                env={str(k): str(v) for k, v in (raw.get("env") or {}).items()},
                cwd=raw.get("cwd"),
                startup_timeout=float(raw.get("startup_timeout", 8)),
                request_timeout=float(request_timeout),
                enabled=True,
                allowed_tools=["duckduckgo_web_search"],
            ),
            None,
        )

    def _render_result(self, result: dict[str, Any]) -> str:
        content = result.get("content", [])
        chunks: list[str] = []
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
                else:
                    chunks.append(json.dumps(item, ensure_ascii=False))
        structured = result.get("structuredContent")
        if structured is not None:
            chunks.append(json.dumps(structured, ensure_ascii=False, indent=2))
        if not chunks:
            chunks.append(json.dumps(result, ensure_ascii=False, indent=2))
        return "\n".join(chunks)
