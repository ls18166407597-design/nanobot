import json
from typing import Any, Dict, List, Optional

import httpx
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.config.loader import get_data_dir


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
        config_path = get_data_dir() / "weather_config.json"
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
                    # GeoAPI domain discovery
                    # Based on tests, geoapi.qweather.com is return 404 for some reason.
                    # We will try the user's custom host AND geoapi.qweather.com
                    found = False
                    for geo_domain in [host, "geoapi.qweather.com"]:
                        # QWeather v2 GeoAPI path
                        geo_url = f"https://{geo_domain}/v2/city/lookup"
                        try:
                            geo_resp = await client.get(geo_url, params={"location": location, "key": key, "lang": lang})
                            if geo_resp.status_code == 200:
                                geo_data = geo_resp.json()
                                if geo_data.get("code") == "200" and geo_data.get("location"):
                                    loc_info = geo_data["location"][0]
                                    location_id = loc_info["id"]
                                    location_name = f"{loc_info.get('adm2', loc_info.get('adm1', ''))} {loc_info['name']}"
                                    found = True
                                    break
                        except Exception:
                            continue
                    
                    if not found:
                        # Final fallback: search might be needed on devapi as well if subscription differs
                        try:
                            geo_url = f"https://devapi.qweather.com/v2/city/lookup"
                            geo_resp = await client.get(geo_url, params={"location": location, "key": key, "lang": lang})
                            if geo_resp.status_code == 200:
                                geo_data = geo_resp.json()
                                if geo_data.get("code") == "200" and geo_data.get("location"):
                                    loc_info = geo_data["location"][0]
                                    location_id = loc_info["id"]
                                    location_name = f"{loc_info.get('adm2', loc_info.get('adm1', ''))} {loc_info['name']}"
                                    found = True
                        except Exception:
                            pass

                    if not found:
                         return ToolResult(success=False, output=f"无法解析城市 '{location}'。请提供 9 位城市 ID，如北京是 101010100。")

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
