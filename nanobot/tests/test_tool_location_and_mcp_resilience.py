import pytest

from nanobot.agent.location_utils import location_query_variants
from nanobot.agent.tools.amap import AmapTool
from nanobot.agent.tools.github import GitHubTool
from nanobot.agent.tools.train_ticket import TrainTicketTool
from nanobot.agent.tools.weather import WeatherTool


def test_weather_pick_best_location_prefers_county_over_city():
    tool = WeatherTool()
    locs = [
        {"id": "101040100", "name": "重庆", "adm1": "重庆市", "adm2": "重庆"},
        {"id": "101042400", "name": "忠县", "adm1": "重庆市", "adm2": "重庆"},
    ]
    best = tool._pick_best_location("重庆市忠县汝溪镇", locs)
    assert best["id"] == "101042400"


def test_location_query_variants_can_degrade_to_city_county():
    variants = location_query_variants("重庆市忠县汝溪镇")
    assert "重庆市忠县汝溪镇" in variants
    assert "重庆市忠县" in variants or "忠县" in variants


@pytest.mark.asyncio
async def test_train_ticket_resolve_city_not_found_returns_failure(monkeypatch):
    tool = TrainTicketTool()

    async def _fake_call(*args, **kwargs):
        return '{"忠县":{"error":"未检索到城市。"}}', None

    monkeypatch.setattr(tool, "_call", _fake_call)
    out = await tool._resolve_city(None, "忠县")  # type: ignore[arg-type]
    assert out.success is False
    assert "未找到城市" in out.output


@pytest.mark.asyncio
async def test_train_ticket_resolve_city_fallback_to_broader_query(monkeypatch):
    tool = TrainTicketTool()
    calls: list[str] = []

    async def _fake_call(_cfg, _tool_name, arguments):
        city = str(arguments.get("citys", ""))
        calls.append(city)
        if city in {"重庆市忠县", "忠县"}:
            return '{"忠县":{"station_code":"ZXW","station_name":"忠县"}}', None
        return '{"重庆市忠县汝溪镇":{"error":"未检索到城市。"}}', None

    monkeypatch.setattr(tool, "_call", _fake_call)
    out = await tool._resolve_city(None, "重庆市忠县汝溪镇")  # type: ignore[arg-type]
    assert out.success is True
    assert "ZXW" in out.output
    assert len(calls) >= 2


def test_github_retryable_error_detector():
    tool = GitHubTool()
    assert tool._is_retryable_error(RuntimeError("MCP error -32603: fetch failed")) is True
    assert tool._is_retryable_error(RuntimeError("permission denied")) is False


def test_amap_location_attempts_expand_for_weather_city():
    tool = AmapTool()
    attempts = tool._expand_location_attempts(
        "maps_weather",
        {"city": "重庆市忠县汝溪镇", "extensions": "all"},
        {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    )
    assert len(attempts) >= 2
    assert attempts[0]["city"] == "重庆市忠县汝溪镇"
    assert any(a.get("city") in {"重庆市忠县", "忠县"} for a in attempts[1:])


def test_amap_missing_required_detected_after_alias_normalize():
    tool = AmapTool()
    schema = {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}
    args = tool._normalize_arguments_by_schema({"location": "重庆"}, schema)
    missing = tool._missing_required_args(args, schema)
    assert args.get("city") == "重庆"
    assert missing == []


def test_amap_weather_result_too_broad_detector():
    tool = AmapTool()
    assert tool._weather_result_too_broad("重庆市忠县汝溪镇", '{"city":"重庆市"}') is True
    assert tool._weather_result_too_broad("重庆市忠县汝溪镇", '{"city":"忠县"}') is False
