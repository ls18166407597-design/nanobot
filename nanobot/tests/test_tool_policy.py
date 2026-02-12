import json

from nanobot.agent.tool_policy import ToolPolicy


def _defs(*names: str):
    return [{"type": "function", "function": {"name": n, "description": n, "parameters": {"type": "object"}}} for n in names]


def _names(defs):
    return [d["function"]["name"] for d in defs]


def test_tool_policy_default_prefers_tavily():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我查一下明天黄金价格"}],
        tool_definitions=_defs("tavily", "browser", "mcp", "read_file"),
        failed_tools=set(),
    )
    assert _names(out) == ["tavily", "read_file"]


def test_tool_policy_browser_query_prefers_browser():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "打开这个网页并点击登录按钮"}],
        tool_definitions=_defs("tavily", "browser", "mcp"),
        failed_tools=set(),
    )
    assert _names(out) == ["browser"]


def test_tool_policy_allows_mcp_only_when_explicit_or_fallback():
    policy = ToolPolicy()
    out1 = policy.filter_tools(
        messages=[{"role": "user", "content": "请用mcp查一下这个问题"}],
        tool_definitions=_defs("tavily", "browser", "mcp"),
        failed_tools=set(),
    )
    assert "mcp" in _names(out1)

    out2 = policy.filter_tools(
        messages=[{"role": "user", "content": "查一下这个问题"}],
        tool_definitions=_defs("tavily", "browser", "mcp"),
        failed_tools={"tavily", "browser"},
    )
    assert "mcp" in _names(out2)


def test_tool_policy_configurable_defaults_and_mcp_toggle():
    policy = ToolPolicy(web_default="browser", enable_mcp_fallback=False, allow_explicit_mcp=False)
    out1 = policy.filter_tools(
        messages=[{"role": "user", "content": "查一下这个问题"}],
        tool_definitions=_defs("tavily", "browser", "mcp"),
        failed_tools=set(),
    )
    assert _names(out1) == ["browser"]

    out2 = policy.filter_tools(
        messages=[{"role": "user", "content": "请用mcp查一下"}],
        tool_definitions=_defs("tavily", "browser", "mcp"),
        failed_tools={"tavily", "browser"},
    )
    assert "mcp" not in _names(out2)


def test_tool_policy_domain_route_train_prefers_mcp():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我查一下12306火车票余票"}],
        tool_definitions=_defs("tavily", "browser", "mcp", "read_file"),
        failed_tools=set(),
    )
    assert _names(out) == ["mcp", "read_file"]


def test_tool_policy_domain_route_train_fallback_to_web_after_mcp_fail():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我查一下12306火车票余票"}],
        tool_definitions=_defs("tavily", "browser", "mcp"),
        failed_tools={"mcp"},
    )
    assert _names(out) == ["tavily"]


def test_tool_policy_domain_route_github_prefers_github_tool():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我看一下这个仓库的PR和issue"}],
        tool_definitions=_defs("github", "tavily", "browser", "mcp"),
        failed_tools=set(),
    )
    assert _names(out) == ["github"]


def test_tool_policy_new_domain_via_config_and_mcp_capabilities(tmp_path, monkeypatch):
    home = tmp_path / ".home"
    cfg_dir = home / "tool_configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "mcp_config.json").write_text(
        json.dumps(
            {
                "servers": {
                    "flight": {
                        "command": "npx",
                        "args": ["-y", "flight-mcp"],
                        "enabled": True,
                        "capabilities": ["flight_ticket"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NANOBOT_HOME", str(home))
    policy = ToolPolicy(
        intent_rules=[{"capability": "flight_ticket", "keywords": ["机票", "航班"]}],
        tool_capabilities={},
    )
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我查明天机票"}],
        tool_definitions=_defs("mcp", "tavily", "browser"),
        failed_tools=set(),
    )
    assert _names(out) == ["mcp"]
