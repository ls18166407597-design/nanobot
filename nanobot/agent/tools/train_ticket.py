"""Train ticket query tool backed by 12306 MCP server."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from nanobot.agent.location_utils import location_query_variants
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.mcp import MCPServerConfig, MCPStdioClient
from nanobot.utils.helpers import get_tool_config_path


class TrainTicketTool(Tool):
    """Stable train ticket querying tool for 12306."""

    name = "train_ticket"
    description = "查询 12306 火车票。提供统一参数，不需要手动处理车站编码。"

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "resolve_city", "resolve_station", "list_city_stations"],
            },
            "from_city": {"type": "string", "description": "出发城市（search 必填）"},
            "to_city": {"type": "string", "description": "到达城市（search 必填）"},
            "date": {"type": "string", "description": "日期：YYYY-MM-DD / 今天 / 明天 / 后天"},
            "from_station": {"type": "string", "description": "可选，指定出发站名"},
            "to_station": {"type": "string", "description": "可选，指定到达站名"},
            "train_types": {"type": "string", "description": "可选，车次筛选：G/D/Z/T/K/O/F/S"},
            "limit": {"type": "integer", "minimum": 0, "maximum": 100, "description": "返回条数限制"},
            "sort": {
                "type": "string",
                "description": "可选排序：startTime/arriveTime/duration",
            },
            "city": {"type": "string", "description": "用于 resolve_city/list_city_stations"},
            "station_name": {"type": "string", "description": "用于 resolve_station"},
        },
        "required": ["action"],
    }

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        cfg, err = self._build_12306_server_config()
        if err:
            return ToolResult(success=False, output=err)

        if action == "search":
            return await self._search(cfg, **kwargs)
        if action == "resolve_city":
            city = str(kwargs.get("city", "")).strip()
            if not city:
                return ToolResult(success=False, output="Error: city is required for resolve_city.")
            return await self._resolve_city(cfg, city)
        if action == "resolve_station":
            station_name = str(kwargs.get("station_name", "")).strip()
            if not station_name:
                return ToolResult(success=False, output="Error: station_name is required for resolve_station.")
            return await self._resolve_station(cfg, station_name)
        if action == "list_city_stations":
            city = str(kwargs.get("city", "")).strip()
            if not city:
                return ToolResult(success=False, output="Error: city is required for list_city_stations.")
            return await self._list_city_stations(cfg, city)
        return ToolResult(success=False, output=f"Error: unsupported action '{action}'.")

    async def _search(self, cfg: MCPServerConfig, **kwargs: Any) -> ToolResult:
        from_city = str(kwargs.get("from_city", "")).strip()
        to_city = str(kwargs.get("to_city", "")).strip()
        date_raw = str(kwargs.get("date", "")).strip()
        from_station = str(kwargs.get("from_station", "")).strip()
        to_station = str(kwargs.get("to_station", "")).strip()

        if not from_city or not to_city:
            return ToolResult(
                success=False,
                output="Error: from_city and to_city are required.",
                remedy="请提供出发城市和到达城市，例如 from_city='上海', to_city='杭州'。",
            )

        normalized_date, date_err = self._normalize_date(date_raw)
        if date_err:
            return ToolResult(success=False, output=f"Error: {date_err}")

        if from_station:
            from_code, err = await self._resolve_station_code(cfg, from_station)
        else:
            from_code, err = await self._resolve_city_code(cfg, from_city)
        if err:
            return ToolResult(success=False, output=f"Error resolving from station: {err}")

        if to_station:
            to_code, err = await self._resolve_station_code(cfg, to_station)
        else:
            to_code, err = await self._resolve_city_code(cfg, to_city)
        if err:
            return ToolResult(success=False, output=f"Error resolving to station: {err}")

        train_types = self._normalize_train_types(str(kwargs.get("train_types", "")).strip())
        limited_num = int(kwargs.get("limit", 20) or 0)
        sort_flag = str(kwargs.get("sort", "")).strip()
        if sort_flag not in {"", "startTime", "arriveTime", "duration"}:
            sort_flag = ""

        args = {
            "date": normalized_date,
            "fromStation": from_code,
            "toStation": to_code,
            "trainFilterFlags": train_types,
            "limitedNum": limited_num,
            "sortFlag": sort_flag,
            "format": "text",
        }
        out, err = await self._call(cfg, "get-tickets", args)
        if err:
            return ToolResult(success=False, output=f"Error querying tickets: {err}")

        header = (
            f"12306 查询结果\n"
            f"- 出发: {from_station or from_city} ({from_code})\n"
            f"- 到达: {to_station or to_city} ({to_code})\n"
            f"- 日期: {normalized_date}"
        )
        return ToolResult(success=True, output=f"{header}\n\n{out}".strip())

    async def _resolve_city(self, cfg: MCPServerConfig, city: str) -> ToolResult:
        out, err = await self._resolve_city_out(cfg, city)
        if err:
            return ToolResult(success=False, output=f"Error resolving city '{city}': {err}")
        return ToolResult(success=True, output=out)

    async def _resolve_station(self, cfg: MCPServerConfig, station_name: str) -> ToolResult:
        out, err = await self._call(cfg, "get-station-code-by-names", {"stationNames": station_name})
        if err:
            return ToolResult(success=False, output=f"Error resolving station '{station_name}': {err}")
        if self._looks_like_not_found(out):
            return ToolResult(
                success=False,
                output=f"未找到车站编码: {station_name}",
                remedy="请确认站名完整准确（例如“重庆北”“上海虹桥”）。",
            )
        return ToolResult(success=True, output=out)

    async def _list_city_stations(self, cfg: MCPServerConfig, city: str) -> ToolResult:
        out, err = await self._call(cfg, "get-stations-code-in-city", {"city": city})
        if err:
            return ToolResult(success=False, output=f"Error listing city stations for '{city}': {err}")
        if self._looks_like_not_found(out):
            return ToolResult(
                success=False,
                output=f"未找到城市下属车站: {city}",
                remedy="请改用地级市名称重试。",
            )
        return ToolResult(success=True, output=out)

    async def _resolve_city_code(self, cfg: MCPServerConfig, city: str) -> tuple[str | None, str | None]:
        out, err = await self._resolve_city_out(cfg, city)
        if err:
            return None, err
        code = self._extract_station_code(out)
        if not code:
            return None, f"city '{city}' station_code not found in MCP result."
        return code, None

    async def _resolve_station_code(self, cfg: MCPServerConfig, station_name: str) -> tuple[str | None, str | None]:
        out, err = await self._call(cfg, "get-station-code-by-names", {"stationNames": station_name})
        if err:
            return None, err
        code = self._extract_station_code(out)
        if not code:
            return None, f"station '{station_name}' station_code not found in MCP result."
        return code, None

    async def _call(
        self, cfg: MCPServerConfig, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[str, str | None]:
        try:
            async with MCPStdioClient(cfg) as client:
                await client.initialize()
                result = await client.request("tools/call", {"name": tool_name, "arguments": arguments})
        except Exception as e:
            return "", str(e)

        output = self._render_result(result)
        if bool(result.get("isError", False)):
            return output, output
        return output, None

    def _build_12306_server_config(self) -> tuple[MCPServerConfig | None, str | None]:
        path = get_tool_config_path("mcp_config.json")
        if not path.exists():
            return None, "Error: mcp_config.json not found."
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            return None, f"Error: failed to parse mcp_config.json: {e}"

        raw = (cfg.get("servers") or {}).get("12306")
        if not isinstance(raw, dict):
            return None, "Error: MCP server '12306' not found in mcp_config.json."
        if not bool(raw.get("enabled", True)):
            return None, "Error: MCP server '12306' is disabled."
        command = str(raw.get("command", "")).strip()
        if not command:
            return None, "Error: MCP server '12306' command is empty."

        return (
            MCPServerConfig(
                command=command,
                args=[str(x) for x in (raw.get("args") or [])],
                env={str(k): str(v) for k, v in (raw.get("env") or {}).items()},
                cwd=raw.get("cwd"),
                startup_timeout=float(raw.get("startup_timeout", 15)),
                request_timeout=float(raw.get("request_timeout", 30)),
                enabled=True,
                allowed_tools=[str(x) for x in (raw.get("allowed_tools") or [])],
            ),
            None,
        )

    def _normalize_date(self, raw: str) -> tuple[str, str | None]:
        text = (raw or "").strip()
        now = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        if not text or text == "今天":
            return now.strftime("%Y-%m-%d"), None
        if text == "明天":
            return (now + timedelta(days=1)).strftime("%Y-%m-%d"), None
        if text == "后天":
            return (now + timedelta(days=2)).strftime("%Y-%m-%d"), None
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})", text)
        if m:
            return m.group(1), None
        return "", "date must be YYYY-MM-DD / 今天 / 明天 / 后天."

    def _normalize_train_types(self, raw: str) -> str:
        if not raw:
            return ""
        mapping = {"高铁": "G", "动车": "D", "直达": "Z", "特快": "T", "快速": "K", "复兴号": "F"}
        normalized = raw
        for k, v in mapping.items():
            normalized = normalized.replace(k, v)
        normalized = normalized.upper()
        flags = "".join(ch for ch in normalized if ch in set("GDZTKOFS"))
        seen = set()
        return "".join(ch for ch in flags if not (ch in seen or seen.add(ch)))

    def _extract_station_code(self, text: str) -> str | None:
        # Expected patterns in 12306 MCP output include "station_code":"SHH" or "station_code: SHH".
        m = re.search(r'"station_code"\s*:\s*"([A-Z]{2,4})"', text)
        if m:
            return m.group(1)
        m = re.search(r"station_code\s*[:=]\s*([A-Z]{2,4})", text)
        if m:
            return m.group(1)
        m = re.search(r"\b([A-Z]{2,4})\b", text)
        return m.group(1) if m else None

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

    def _looks_like_not_found(self, text: str) -> bool:
        lowered = text.lower()
        markers = [
            "未检索到城市",
            "未检索到车站",
            "not found",
            "no result",
            "\"error\"",
        ]
        return any(m in lowered for m in markers)

    async def _resolve_city_out(self, cfg: MCPServerConfig, city: str) -> tuple[str, str | None]:
        last_err: str | None = None
        for query in location_query_variants(city):
            out, err = await self._call(cfg, "get-station-code-of-citys", {"citys": query})
            if err:
                last_err = err
                continue
            if self._looks_like_not_found(out):
                last_err = (
                    f"未找到城市/车站编码: {city}。请改用地级市名称（如“重庆”“万州”），"
                    "或直接给出车站名（如“重庆北”）。"
                )
                continue
            return out, None
        return "", last_err or f"city '{city}' station_code not found."
