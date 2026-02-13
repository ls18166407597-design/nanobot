import json
from typing import Any, Dict, List, Optional

import httpx
from nanobot.agent.location_utils import location_query_variants, score_geo_candidate
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.utils.helpers import get_tool_config_path


class WeatherTool(Tool):
    """Tool for retrieving weather information from QWeather."""

    name = "weather"
    description = """
    Get real-time weather, forecasts, and lifestyle indices from QWeather.
    Supports searching by city names (e.g., '北京', 'Shanghai') or Location IDs.
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["now", "forecast", "indices", "search"],
                "description": "The weather action to perform.",
            },
            "location": {
                "type": "string",
                "description": "City name or Location ID (e.g., '北京', '101010100').",
            },
            "lang": {
                "type": "string",
                "default": "zh",
                "description": "Language for the response (default: zh).",
            },
        },
        "required": ["action", "location"],
    }

    def _load_config(self) -> Optional[Dict[str, str]]:
        config_path = get_tool_config_path("weather_config.json")
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    async def execute(self, action: str, location: str, lang: str = "zh", **kwargs: Any) -> ToolResult:
        config = self._load_config()
        if not config:
            return ToolResult(
                success=False,
                output="Error: QWeather not configured.",
                remedy="请在 weather_config.json 中配置 key（可选 host）。"
            )

        key = config.get("key")
        host = config.get("host", "devapi.qweather.com")
        if not key:
            return ToolResult(
                success=False,
                output="Error: QWeather key is missing.",
                remedy="请在 weather_config.json 中添加 key 字段。"
            )
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            try:
                # 1. Resolve Location ID
                location_id = location
                location_name = location
                if not location.isdigit():
                    # GeoAPI domain discovery.
                    # Some keys are bound to a custom host; use that first.
                    found = False
                    variants = location_query_variants(location)
                    for query in variants:
                        for geo_domain in [host, "geoapi.qweather.com", "devapi.qweather.com"]:
                            # Official endpoint is /geo/v2/city/lookup.
                            # Keep legacy /v2 path as fallback for provider-side compatibility.
                            for geo_path in ["/geo/v2/city/lookup", "/v2/city/lookup"]:
                                geo_url = f"https://{geo_domain}{geo_path}"
                                try:
                                    geo_resp = await client.get(
                                        geo_url,
                                        params={"location": query, "key": key, "lang": lang, "number": 10},
                                    )
                                    if geo_resp.status_code == 200:
                                        geo_data = geo_resp.json()
                                        locs = geo_data.get("location") or []
                                        if geo_data.get("code") == "200" and isinstance(locs, list) and locs:
                                            loc_info = self._pick_best_location(location, locs)
                                            location_id = str(loc_info.get("id", "")).strip()
                                            display_parts = [
                                                str(loc_info.get("adm1", "")).strip(),
                                                str(loc_info.get("adm2", "")).strip(),
                                                str(loc_info.get("name", "")).strip(),
                                            ]
                                            location_name = " ".join([x for x in display_parts if x]).strip() or query
                                            if location_id:
                                                found = True
                                                break
                                except Exception:
                                    continue
                            if found:
                                break
                        if found:
                            break
                    
                    if not found:
                        return ToolResult(
                            success=False,
                            output=(
                                f"无法解析地点 '{location}'。当前天气接口通常支持到区县/城市级，"
                                "乡镇名称可能无法直接识别。"
                            ),
                            remedy="请改用“市/区县”名称，或提供 9 位地点 ID（如北京 101010100）。",
                        )

                # 2. Weather Action
                base_url = f"https://{host}/v7"
                params = {"location": location_id, "key": key, "lang": lang}

                if action == "now":
                    resp = await client.get(f"{base_url}/weather/now", params=params)
                    data = resp.json()
                    if data.get("code") != "200":
                        return ToolResult(success=False, output=f"天气查询失败: {data.get('code')}")
                    
                    now = data["now"]
                    output = [
                        f"📍 城市: {location_name}",
                        f"🌡️ 温度: {now['temp']}°C (体感 {now['feelsLike']}°C)",
                        f"☁️ 天气: {now['text']}",
                        f"💨 风力: {now['windDir']} {now['windScale']}级",
                        f"🕒 观测时间: {now['obsTime']}"
                    ]
                    return ToolResult(success=True, output="\n".join(output))

                elif action == "forecast":
                    resp = await client.get(f"{base_url}/weather/3d", params=params)
                    data = resp.json()
                    if data.get("code") != "200":
                        return ToolResult(success=False, output=f"预报查询失败: {data.get('code')}")
                    output = [f"📅 {location_name} 3日天气预报:"]
                    for day in data["daily"]:
                        output.append(f"- {day['fxDate']}: {day['textDay']}转{day['textNight']}, {day['tempMin']}~{day['tempMax']}°C")
                    return ToolResult(success=True, output="\n".join(output))

                elif action == "indices":
                    resp = await client.get(f"{base_url}/indices/1d", params={**params, "type": "1,3,5"})
                    data = resp.json()
                    if data.get("code") != "200":
                        return ToolResult(success=False, output=f"指数查询失败: {data.get('code')}")
                    output = [f"💡 {location_name} 生活建议:"]
                    for item in data["daily"]:
                        output.append(f"- {item['name']}: {item['category']}。{item['text']}")
                    return ToolResult(success=True, output="\n".join(output))

                elif action == "search":
                    return ToolResult(success=True, output=f"已找到 {location_name}，ID 为 {location_id}")

                return ToolResult(success=False, output=f"未知动作: {action}")

            except Exception as e:
                return ToolResult(success=False, output=f"Weather Tool Error: {str(e)}")

    def _pick_best_location(self, query: str, locs: List[Dict[str, Any]]) -> Dict[str, Any]:
        return max(locs, key=lambda item: score_geo_candidate(query, item))
