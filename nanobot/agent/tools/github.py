"""GitHub tool backed by MCP server."""

from __future__ import annotations

import json
import asyncio
from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.mcp import MCPServerConfig, MCPStdioClient
from nanobot.utils.helpers import get_tool_config_path


class GitHubTool(Tool):
    """GitHub operations via MCP server."""

    name = "github"
    description = (
        "GitHub MCP wrapper. "
        "Use action='list_tools' to inspect supported MCP tools, "
        "then action='call_tool' to execute one tool."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["setup", "list_tools", "call_tool"],
                "description": "setup: save token. list_tools/call_tool: use MCP server 'github'.",
            },
            "mcp_tool": {"type": "string", "description": "MCP tool name (required for call_tool)."},
            "arguments": {"type": "object", "description": "Arguments for MCP tool call."},
            "setup_token": {"type": "string", "description": "GitHub token for setup."},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 120},
        },
        "required": ["action"],
    }

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        if action == "setup":
            token = str(kwargs.get("setup_token", "")).strip()
            if not token:
                return ToolResult(
                    success=False,
                    output="Error: 'setup_token' is required for setup.",
                    remedy="请提供 GitHub PAT：action='setup', setup_token='ghp_...'",
                )
            self._save_github_token(token)
            return ToolResult(success=True, output="GitHub token saved to github_config.json.")

        server_cfg, err = self._build_github_server_config(timeout=kwargs.get("timeout"))
        if err:
            return ToolResult(success=False, output=err)

        if action == "list_tools":
            return await self._list_tools(server_cfg)

        if action == "call_tool":
            tool_name = str(kwargs.get("mcp_tool", "")).strip()
            if not tool_name:
                return ToolResult(
                    success=False,
                    output="Error: 'mcp_tool' is required for call_tool.",
                    remedy="先调用 action='list_tools' 查看可用工具，再指定 mcp_tool。",
                )
            args = kwargs.get("arguments") or {}
            if not isinstance(args, dict):
                return ToolResult(success=False, output="Error: 'arguments' must be an object.")
            return await self._call_tool(server_cfg, tool_name=tool_name, arguments=args)

        return ToolResult(success=False, output=f"Unknown action: {action}")

    async def _list_tools(self, cfg: MCPServerConfig) -> ToolResult:
        result: dict[str, Any] | None = None
        last_err: Exception | None = None
        for attempt in range(1, 3):
            try:
                async with MCPStdioClient(cfg) as client:
                    await client.initialize()
                    result = await client.request("tools/list", {})
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt >= 2 or not self._is_retryable_error(e):
                    break
                await asyncio.sleep(0.6 * attempt)
        if last_err is not None:
            return ToolResult(success=False, output=f"Error listing GitHub MCP tools: {last_err}")
        if result is None:
            return ToolResult(success=False, output="Error listing GitHub MCP tools: empty response.")

        tools = result.get("tools", [])
        if not isinstance(tools, list) or not tools:
            return ToolResult(success=True, output="GitHub MCP server returned no tools.")
        lines = ["GitHub MCP tools:"]
        for item in tools:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "unknown"))
            desc = str(item.get("description", "")).strip()
            lines.append(f"- {name}: {desc}" if desc else f"- {name}")
        return ToolResult(success=True, output="\n".join(lines))

    async def _call_tool(self, cfg: MCPServerConfig, *, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        result: dict[str, Any] | None = None
        last_err: Exception | None = None
        for attempt in range(1, 3):
            try:
                async with MCPStdioClient(cfg) as client:
                    await client.initialize()
                    result = await client.request(
                        "tools/call",
                        {"name": tool_name, "arguments": arguments},
                    )
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt >= 2 or not self._is_retryable_error(e):
                    break
                await asyncio.sleep(0.6 * attempt)
        if last_err is not None:
            return ToolResult(success=False, output=f"Error calling GitHub MCP tool '{tool_name}': {last_err}")
        if result is None:
            return ToolResult(success=False, output=f"Error calling GitHub MCP tool '{tool_name}': empty response.")

        is_error = bool(result.get("isError", False))
        output = self._render_result(result)
        return ToolResult(success=not is_error, output=output)

    def _is_retryable_error(self, err: Exception) -> bool:
        text = str(err).lower()
        retryable_tokens = [
            "fetch failed",
            "timeout",
            "timed out",
            "socket hang up",
            "econnreset",
            "ehostunreach",
            "enotfound",
            "eai_again",
            "429",
            "502",
            "503",
            "504",
        ]
        return any(t in text for t in retryable_tokens)

    def _build_github_server_config(self, timeout: int | None) -> tuple[MCPServerConfig | None, str | None]:
        mcp_cfg_path = get_tool_config_path("mcp_config.json")
        if not mcp_cfg_path.exists():
            return None, "Error: mcp_config.json not found."
        try:
            with open(mcp_cfg_path, "r", encoding="utf-8") as f:
                mcp_cfg = json.load(f)
        except Exception as e:
            return None, f"Error: failed to parse mcp_config.json: {e}"

        server_raw = (mcp_cfg.get("servers") or {}).get("github")
        if not isinstance(server_raw, dict):
            return None, "Error: MCP server 'github' not found in mcp_config.json."
        if not bool(server_raw.get("enabled", True)):
            return None, "Error: MCP server 'github' is disabled."

        command = str(server_raw.get("command", "")).strip()
        if not command:
            return None, "Error: MCP server 'github' command is empty."

        env = {str(k): str(v) for k, v in (server_raw.get("env") or {}).items()}
        token = self._load_github_token()
        if token and "GITHUB_TOKEN" not in env:
            env["GITHUB_TOKEN"] = token

        request_timeout = int(server_raw.get("request_timeout", 20))
        if timeout is not None:
            request_timeout = max(1, min(120, int(timeout)))

        return (
            MCPServerConfig(
                command=command,
                args=[str(x) for x in (server_raw.get("args") or [])],
                env=env,
                cwd=server_raw.get("cwd"),
                startup_timeout=float(server_raw.get("startup_timeout", 8)),
                request_timeout=float(request_timeout),
                enabled=True,
                allowed_tools=[str(x) for x in (server_raw.get("allowed_tools") or [])],
            ),
            None,
        )

    def _load_github_token(self) -> str | None:
        path = get_tool_config_path("github_config.json")
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            token = str(data.get("token", "")).strip()
            return token or None
        except Exception:
            return None

    def _save_github_token(self, token: str) -> None:
        path = get_tool_config_path("github_config.json", for_write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"token": token}, f, ensure_ascii=False, indent=2)

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
