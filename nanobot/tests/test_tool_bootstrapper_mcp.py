from pathlib import Path
from types import SimpleNamespace

from nanobot.agent.tool_bootstrapper import ToolBootstrapper


class _ToolsStub:
    def __init__(self):
        self.items: dict[str, object] = {}

    def register(self, tool):
        self.items[tool.name] = tool

    def get(self, name: str):
        return self.items.get(name)


def _make_tools_config():
    return SimpleNamespace(
        enabled_tools=["mcp"],
        disabled_tools=[],
        mcp=SimpleNamespace(startup_timeout=8, request_timeout=20, max_output_chars=12000),
    )


def _build_bootstrapper(tools, workspace: Path):
    return ToolBootstrapper(
        tools=tools,
        workspace=workspace,
        restrict_to_workspace=False,
        exec_config=SimpleNamespace(timeout=60, mode="host", sandbox_engine="auto"),
        provider=None,
        brain_config=None,
        web_proxy=None,
        bus_publish_outbound=None,
        cron_service=None,
        model_registry=None,
        tools_config=_make_tools_config(),
        mac_confirm_mode="warn",
    )


def test_mcp_tool_not_registered_when_no_server_config(tmp_path, monkeypatch):
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path / ".home"))
    tools = _ToolsStub()
    bootstrapper = _build_bootstrapper(tools, workspace=tmp_path)
    bootstrapper.register_default_tools()
    assert "mcp" not in tools.items


def test_mcp_tool_registered_when_enabled_server_exists(tmp_path, monkeypatch):
    home = tmp_path / ".home"
    tool_cfg = home / "tool_configs"
    tool_cfg.mkdir(parents=True, exist_ok=True)
    (tool_cfg / "mcp_config.json").write_text(
        '{"servers":{"demo":{"command":"python","args":["-V"],"enabled":true}}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("NANOBOT_HOME", str(home))
    tools = _ToolsStub()
    bootstrapper = _build_bootstrapper(tools, workspace=tmp_path)
    bootstrapper.register_default_tools()
    assert "mcp" in tools.items
