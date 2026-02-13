"""Amap tool backed by MCP server."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from nanobot.agent.location_utils import location_query_variants
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
    _ARG_ALIASES: dict[str, tuple[str, ...]] = {
        "city": ("location", "place", "region"),
        "address": ("location", "place", "city"),
        "keywords": ("query", "keyword", "q"),
        "location": ("coord", "coords"),
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
            return ToolResult(success=False, output=f"Error listing Amap MCP tools: {last_err}")
        if result is None:
            return ToolResult(success=False, output="Error listing Amap MCP tools: empty response.")

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
        schema = await self._get_tool_schema(cfg, tool_name)
        normalized_args = self._normalize_arguments_by_schema(arguments, schema)
        missing = self._missing_required_args(normalized_args, schema)
        if missing:
            return ToolResult(
                success=False,
                output=f"参数缺失: {', '.join(missing)}",
                remedy=f"请按 {tool_name} 的参数要求补全字段（required={missing}）。",
            )

        # Generic location fallback chain for tools that use textual city/address fields.
        # This allows township-level input to degrade into county/city automatically.
        attempts = self._expand_location_attempts(tool_name, normalized_args, schema)
        last_output = ""
        last_error = ""
        for args_try in attempts:
            ok, output, raw_err = await self._mcp_call_tool(cfg, tool_name=tool_name, arguments=args_try)
            if ok:
                if tool_name == "maps_weather":
                    origin_query = str(arguments.get("city", "")).strip()
                    if self._weather_result_too_broad(origin_query, output):
                        last_output = output
                        continue
                return ToolResult(success=True, output=output)
            last_output, last_error = output, raw_err
            # Not location-related failure -> fail fast.
            if not self._looks_like_location_error(output):
                break

        if last_output:
            return ToolResult(success=False, output=last_output)
        return ToolResult(success=False, output=f"Error calling Amap MCP tool '{tool_name}': {last_error}")

    async def _mcp_call_tool(
        self, cfg: MCPServerConfig, *, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[bool, str, str]:
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
            return False, f"Error calling Amap MCP tool '{tool_name}': {last_err}", str(last_err)
        if result is None:
            return False, f"Error calling Amap MCP tool '{tool_name}': empty response.", "empty response"
        is_error = bool(result.get("isError", False))
        output = self._render_result(result)
        return (not is_error), output, ""

    def _expand_location_attempts(
        self, tool_name: str, arguments: dict[str, Any], schema: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        # Keep original first.
        attempts: list[dict[str, Any]] = [dict(arguments)]
        # Try fallback on common textual location keys.
        schema_props = ((schema or {}).get("properties") or {})
        if isinstance(schema_props, dict) and schema_props:
            location_keys = tuple(
                k
                for k, v in schema_props.items()
                if isinstance(k, str)
                and isinstance(v, dict)
                and v.get("type") == "string"
                and ("city" in k.lower() or "address" in k.lower() or "keyword" in k.lower())
            ) or ("city", "address", "keywords")
        else:
            location_keys = ("city", "address", "keywords")

        for key in location_keys:
            val = arguments.get(key)
            if isinstance(val, str) and val.strip():
                variants = location_query_variants(val)
                for q in variants[1:]:
                    new_args = dict(arguments)
                    new_args[key] = q
                    if new_args not in attempts:
                        attempts.append(new_args)
                break
        return attempts

    def _looks_like_location_error(self, output: str) -> bool:
        text = (output or "").lower()
        markers = [
            "no such location",
            "invalid params",
            "invalid parameter",
            "city not found",
            "address not found",
            "cannot read properties of undefined",
            "reading 'city'",
            "reading \"city\"",
            "adcode",
            "location",
            "未找到",
            "无效",
            "参数",
        ]
        return any(m in text for m in markers)

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

    def _weather_result_too_broad(self, query: str, output: str) -> bool:
        q = (query or "").strip()
        if not q:
            return False
        # If query contains county/district-level token, prefer matching it.
        tokens = re.findall(r"([^省市区县]{1,12}[区县])", q)
        if not tokens:
            return False
        target = tokens[-1]
        city = ""
        try:
            obj = json.loads(output)
            if isinstance(obj, dict):
                city = str(obj.get("city", "")).strip()
        except Exception:
            city = ""
        if not city:
            return False
        return target not in city

    async def _get_tool_schema(self, cfg: MCPServerConfig, tool_name: str) -> dict[str, Any] | None:
        # Lightweight per-process cache.
        cache = getattr(self, "_tool_schema_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._tool_schema_cache = cache
        if tool_name in cache:
            return cache[tool_name]
        try:
            async with MCPStdioClient(cfg) as client:
                await client.initialize()
                result = await client.request("tools/list", {})
            tools = result.get("tools", [])
            if isinstance(tools, list):
                for item in tools:
                    if isinstance(item, dict) and item.get("name") == tool_name:
                        schema = item.get("inputSchema")
                        if isinstance(schema, dict):
                            cache[tool_name] = schema
                            return schema
        except Exception:
            return None
        return None

    def _normalize_arguments_by_schema(
        self, arguments: dict[str, Any], schema: dict[str, Any] | None
    ) -> dict[str, Any]:
        args = dict(arguments)
        if not isinstance(schema, dict):
            return args
        props = schema.get("properties") or {}
        if not isinstance(props, dict):
            return args
        for target, aliases in self._ARG_ALIASES.items():
            if target in props and (target not in args or args.get(target) in (None, "")):
                for src in aliases:
                    val = args.get(src)
                    if isinstance(val, str) and val.strip():
                        args[target] = val
                        break
        return args

    def _missing_required_args(self, arguments: dict[str, Any], schema: dict[str, Any] | None) -> list[str]:
        if not isinstance(schema, dict):
            return []
        required = schema.get("required") or []
        if not isinstance(required, list):
            return []
        missing: list[str] = []
        for key in required:
            if not isinstance(key, str):
                continue
            val = arguments.get(key)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(key)
        return missing

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
