from nanobot.agent.tool_policy import ToolPolicy


def _defs(*names: str):
    return [{"type": "function", "function": {"name": n, "description": n, "parameters": {"type": "object"}}} for n in names]


def _names(defs):
    return [d["function"]["name"] for d in defs]


def test_tool_policy_default_prefers_tavily():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我查一下明天黄金价格"}],
        tool_definitions=_defs("tavily", "browser", "read_file"),
        failed_tools=set(),
    )
    assert _names(out) == ["tavily", "read_file"]


def test_tool_policy_browser_query_prefers_browser():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "打开这个网页并点击登录按钮"}],
        tool_definitions=_defs("tavily", "browser"),
        failed_tools=set(),
    )
    assert _names(out) == ["browser"]


def test_tool_policy_no_direct_mcp_by_default():
    policy = ToolPolicy()
    out1 = policy.filter_tools(
        messages=[{"role": "user", "content": "请用mcp查一下这个问题"}],
        tool_definitions=_defs("tavily", "browser"),
        failed_tools=set(),
    )
    assert "mcp" not in _names(out1)

    out2 = policy.filter_tools(
        messages=[{"role": "user", "content": "查一下这个问题"}],
        tool_definitions=_defs("tavily", "browser"),
        failed_tools={"tavily", "browser"},
    )
    assert _names(out2) == []


def test_tool_policy_configurable_defaults():
    policy = ToolPolicy(web_default="browser")
    out1 = policy.filter_tools(
        messages=[{"role": "user", "content": "查一下这个问题"}],
        tool_definitions=_defs("tavily", "browser"),
        failed_tools=set(),
    )
    assert _names(out1) == ["browser"]


def test_tool_policy_domain_route_train_prefers_dedicated_tool():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我查一下12306火车票余票"}],
        tool_definitions=_defs("train_ticket", "tavily", "browser", "read_file"),
        failed_tools=set(),
    )
    assert _names(out) == ["train_ticket", "read_file"]


def test_tool_policy_domain_route_train_fallback_to_web_after_tool_fail():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我查一下12306火车票余票"}],
        tool_definitions=_defs("train_ticket", "tavily", "browser"),
        failed_tools={"train_ticket"},
    )
    assert _names(out) == ["tavily"]


def test_tool_policy_domain_route_github_prefers_github_tool():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我看一下这个仓库的PR和issue"}],
        tool_definitions=_defs("github", "tavily", "browser"),
        failed_tools=set(),
    )
    assert _names(out) == ["github"]


def test_tool_policy_domain_route_email_prefers_mail_tool():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我看一下邮箱未读邮件"}],
        tool_definitions=_defs("mail", "gmail", "qq_mail", "tavily", "browser"),
        failed_tools=set(),
    )
    assert _names(out) == ["mail", "gmail", "qq_mail"]


def test_tool_policy_new_domain_via_config_maps_to_dedicated_tool():
    policy = ToolPolicy(
        intent_rules=[{"capability": "flight_ticket", "keywords": ["机票", "航班"]}],
        tool_capabilities={"flight_ticket": ["flight_ticket"]},
    )
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "帮我查明天机票"}],
        tool_definitions=_defs("flight_ticket", "tavily", "browser"),
        failed_tools=set(),
    )
    assert _names(out) == ["flight_ticket"]


def test_tool_policy_search_fallback_to_browser_when_tavily_failed():
    policy = ToolPolicy()
    out = policy.filter_tools(
        messages=[{"role": "user", "content": "查一下今天的科技新闻"}],
        tool_definitions=_defs("tavily", "browser", "read_file"),
        failed_tools={"tavily"},
    )
    assert _names(out) == ["browser", "read_file"]
