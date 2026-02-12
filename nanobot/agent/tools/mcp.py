"""MCP tool: list and call external MCP servers via stdio."""

from __future__ import annotations

import json
from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.mcp import MCPServerConfig, MCPStdioClient
from nanobot.utils.helpers import get_tool_config_path


class MCPTool(Tool):
    name = "mcp"
    description = (
        "Call external MCP servers. "
        "Actions: list_servers, list_tools, call_tool. "
        "Config file: .home/tool_configs/mcp_config.json"
    )

    def __init__(self, startup_timeout: int = 8, request_timeout: int = 20, max_output_chars: int = 12000):
        self.startup_timeout = max(1, int(startup_timeout))
        self.request_timeout = max(1, int(request_timeout))
        self.max_output_chars = max(2000, int(max_output_chars))

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_servers", "list_tools", "call_tool"],
                    "description": "Operation type.",
                },
                "server": {"type": "string", "description": "Server name from mcp_config.json."},
                "tool": {"type": "string", "description": "Tool name for action=call_tool."},
                "arguments": {"type": "object", "description": "Arguments passed to MCP tool call."},
                "timeout": {
                    "type": "integer",
                    "description": "Optional per-request timeout in seconds.",
                    "minimum": 1,
                    "maximum": 120,
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        server: str | None = None,
        tool: str | None = None,
        arguments: dict[str, Any] | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        cfg = self._load_config()
        if not cfg:
            return ToolResult(
                success=False,
                output="Error: MCP config not found.",
                remedy="请创建 .home/tool_configs/mcp_config.json 并配置 servers。",
            )

        if action == "list_servers":
            return ToolResult(success=True, output=self._format_servers(cfg))

        if not server:
            return ToolResult(success=False, output="Error: Missing required parameter 'server'.")

        servers = cfg.get("servers", {})
        server_raw = servers.get(server)
        if not isinstance(server_raw, dict):
            return ToolResult(success=False, output=f"Error: MCP server '{server}' not found.")
        server_cfg = self._build_server_config(server_raw)
        if not server_cfg.enabled:
            return ToolResult(success=False, output=f"Error: MCP server '{server}' is disabled.")

        if action == "list_tools":
            return await self._list_tools(server_name=server, server_cfg=server_cfg, timeout=timeout)

        if action == "call_tool":
            if not tool:
                return ToolResult(success=False, output="Error: Missing required parameter 'tool'.")
            return await self._call_tool(
                server_name=server,
                server_cfg=server_cfg,
                tool=tool,
                arguments=arguments or {},
                timeout=timeout,
            )

        return ToolResult(success=False, output=f"Error: Unsupported action '{action}'.")

    def _load_config(self) -> dict[str, Any] | None:
        config_path = get_tool_config_path("mcp_config.json")
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                return None
            return cfg
        except Exception:
            return None

    def _format_servers(self, cfg: dict[str, Any]) -> str:
        servers = cfg.get("servers", {})
        if not isinstance(servers, dict) or not servers:
            return "No MCP servers configured."
        lines = ["MCP servers:"]
        for name in sorted(servers.keys()):
            item = servers.get(name, {})
            command = str(item.get("command", "")).strip()
            enabled = bool(item.get("enabled", True))
            state = "enabled" if enabled else "disabled"
            lines.append(f"- {name} [{state}] command={command or '(missing)'}")
        return "\n".join(lines)

    def _build_server_config(self, raw: dict[str, Any]) -> MCPServerConfig:
        return MCPServerConfig(
            command=str(raw.get("command", "")).strip(),
            args=[str(x) for x in raw.get("args", []) if str(x).strip()],
            env={str(k): str(v) for k, v in raw.get("env", {}).items()},
            cwd=str(raw["cwd"]) if raw.get("cwd") else None,
            startup_timeout=float(raw.get("startup_timeout", self.startup_timeout)),
            request_timeout=float(raw.get("request_timeout", self.request_timeout)),
            enabled=bool(raw.get("enabled", True)),
            allowed_tools=[str(x) for x in raw.get("allowed_tools", []) if str(x).strip()],
        )

    async def _list_tools(self, *, server_name: str, server_cfg: MCPServerConfig, timeout: int | None) -> ToolResult:
        if not server_cfg.command:
            return ToolResult(success=False, output=f"Error: MCP server '{server_name}' command is empty.")
        if timeout is not None:
            server_cfg.request_timeout = float(timeout)
        try:
            async with MCPStdioClient(server_cfg) as client:
                await client.initialize()
                result = await client.request("tools/list", {})
        except Exception as e:
            return ToolResult(success=False, output=f"Error listing MCP tools: {e}")

        tools = result.get("tools", [])
        if not isinstance(tools, list) or not tools:
            return ToolResult(success=True, output=f"MCP server '{server_name}' has no tools.")
        lines = [f"MCP tools on '{server_name}':"]
        for item in tools:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "unknown"))
            desc = str(item.get("description", "")).strip()
            if desc:
                lines.append(f"- {name}: {desc}")
            else:
                lines.append(f"- {name}")
        return ToolResult(success=True, output="\n".join(lines))

    async def _call_tool(
        self,
        *,
        server_name: str,
        server_cfg: MCPServerConfig,
        tool: str,
        arguments: dict[str, Any],
        timeout: int | None,
    ) -> ToolResult:
        if not server_cfg.command:
            return ToolResult(success=False, output=f"Error: MCP server '{server_name}' command is empty.")
        if server_cfg.allowed_tools and tool not in server_cfg.allowed_tools:
            return ToolResult(
                success=False,
                output=f"Error: MCP tool '{tool}' is not allowed on server '{server_name}'.",
                remedy="请在 mcp_config.json 的 allowed_tools 中显式放行该工具。",
            )
        if timeout is not None:
            server_cfg.request_timeout = float(timeout)

        try:
            async with MCPStdioClient(server_cfg) as client:
                await client.initialize()
                result = await client.request("tools/call", {"name": tool, "arguments": arguments or {}})
        except Exception as e:
            return ToolResult(success=False, output=f"Error calling MCP tool '{tool}': {e}")

        is_error = bool(result.get("isError", False))
        output = self._render_call_result(result)
        if len(output) > self.max_output_chars:
            output = output[: self.max_output_chars] + "\n... (truncated)"
        return ToolResult(success=not is_error, output=output)

    def _render_call_result(self, result: dict[str, Any]) -> str:
        content = result.get("content", [])
        chunks: list[str] = []
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text = str(item.get("text", "")).strip()
                    if text:
                        chunks.append(text)
                elif "text" in item:
                    text = str(item.get("text", "")).strip()
                    if text:
                        chunks.append(text)
                else:
                    chunks.append(json.dumps(item, ensure_ascii=False))
        structured = result.get("structuredContent")
        if structured is not None:
            chunks.append(json.dumps(structured, ensure_ascii=False, indent=2))
        if not chunks:
            chunks.append(json.dumps(result, ensure_ascii=False, indent=2))
        return "\n".join(chunks).strip()
