"""Amap tool backed by MCP server."""

from __future__ import annotations

import json
from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.mcp import MCPServerConfig, MCPStdioClient
from nanobot.utils.helpers import get_tool_config_path


class AmapTool(Tool):
    """Amap map/search/route operations via MCP server."""

    name = "amap"
    description = (
        "高德地图 MCP 封装工具。"
        "Use action='list_tools' 查看可用能力，"
        "再用 action='call_tool' 调用具体能力。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["setup", "list_tools", "call_tool"],
                "description": "setup: 保存高德 key。list_tools/call_tool: 使用 mcp server 'amap'。",
            },
            "setup_key": {"type": "string", "description": "高德 Web 服务 Key（用于 setup）"},
            "amap_tool": {"type": "string", "description": "MCP tool 名称（call_tool 必填）"},
            "arguments": {"type": "object", "description": "传给 amap_tool 的参数对象"},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 120},
        },
        "required": ["action"],
    }

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        if action == "setup":
            key = str(kwargs.get("setup_key", "")).strip()
            if not key:
                return ToolResult(
                    success=False,
                    output="Error: 'setup_key' is required for setup.",
                    remedy="请提供高德 Web 服务 Key：action='setup', setup_key='...'",
                )
            self._save_amap_key(key)
            return ToolResult(success=True, output="Amap key saved to amap_config.json.")

        server_cfg, err = self._build_amap_server_config(timeout=kwargs.get("timeout"))
        if err:
            return ToolResult(success=False, output=err)

        if action == "list_tools":
            return await self._list_tools(server_cfg)

        if action == "call_tool":
            tool_name = str(kwargs.get("amap_tool", "")).strip()
            if not tool_name:
                return ToolResult(
                    success=False,
                    output="Error: 'amap_tool' is required for call_tool.",
                    remedy="先调用 action='list_tools' 查看可用工具，再指定 amap_tool。",
                )
            args = kwargs.get("arguments") or {}
            if not isinstance(args, dict):
                return ToolResult(success=False, output="Error: 'arguments' must be an object.")
            return await self._call_tool(server_cfg, tool_name=tool_name, arguments=args)

        return ToolResult(success=False, output=f"Unknown action: {action}")

    async def _list_tools(self, cfg: MCPServerConfig) -> ToolResult:
        try:
            async with MCPStdioClient(cfg) as client:
                await client.initialize()
                result = await client.request("tools/list", {})
        except Exception as e:
            return ToolResult(success=False, output=f"Error listing Amap MCP tools: {e}")

        tools = result.get("tools", [])
        if not isinstance(tools, list) or not tools:
            return ToolResult(success=True, output="Amap MCP server returned no tools.")
        lines = ["Amap MCP tools:"]
        for item in tools:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "unknown"))
            desc = str(item.get("description", "")).strip()
            lines.append(f"- {name}: {desc}" if desc else f"- {name}")
        return ToolResult(success=True, output="\n".join(lines))

    async def _call_tool(self, cfg: MCPServerConfig, *, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        try:
            async with MCPStdioClient(cfg) as client:
                await client.initialize()
                result = await client.request(
                    "tools/call",
                    {"name": tool_name, "arguments": arguments},
                )
        except Exception as e:
            return ToolResult(success=False, output=f"Error calling Amap MCP tool '{tool_name}': {e}")

        is_error = bool(result.get("isError", False))
        output = self._render_result(result)
        return ToolResult(success=not is_error, output=output)

    def _build_amap_server_config(self, timeout: int | None) -> tuple[MCPServerConfig | None, str | None]:
        mcp_cfg_path = get_tool_config_path("mcp_config.json")
        if not mcp_cfg_path.exists():
            return None, "Error: mcp_config.json not found."
        try:
            with open(mcp_cfg_path, "r", encoding="utf-8") as f:
                mcp_cfg = json.load(f)
        except Exception as e:
            return None, f"Error: failed to parse mcp_config.json: {e}"

        server_raw = (mcp_cfg.get("servers") or {}).get("amap")
        if not isinstance(server_raw, dict):
            return None, "Error: MCP server 'amap' not found in mcp_config.json."
        if not bool(server_raw.get("enabled", True)):
            return None, "Error: MCP server 'amap' is disabled."

        command = str(server_raw.get("command", "")).strip()
        if not command:
            return None, "Error: MCP server 'amap' command is empty."

        env = {str(k): str(v) for k, v in (server_raw.get("env") or {}).items()}
        key = self._load_amap_key()
        if key and "AMAP_MAPS_API_KEY" not in env:
            env["AMAP_MAPS_API_KEY"] = key

        request_timeout = int(server_raw.get("request_timeout", 30))
        if timeout is not None:
            request_timeout = max(1, min(120, int(timeout)))

        return (
            MCPServerConfig(
                command=command,
                args=[str(x) for x in (server_raw.get("args") or [])],
                env=env,
                cwd=server_raw.get("cwd"),
                startup_timeout=float(server_raw.get("startup_timeout", 15)),
                request_timeout=float(request_timeout),
                enabled=True,
                allowed_tools=[str(x) for x in (server_raw.get("allowed_tools") or [])],
            ),
            None,
        )

    def _load_amap_key(self) -> str | None:
        path = get_tool_config_path("amap_config.json")
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            key = str(data.get("api_key", "")).strip()
            return key or None
        except Exception:
            return None

    def _save_amap_key(self, key: str) -> None:
        path = get_tool_config_path("amap_config.json", for_write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"api_key": key}, f, ensure_ascii=False, indent=2)

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
