import pytest

from nanobot.agent.tools.mac import MacTool
from nanobot.agent.tools import mac_vision
from nanobot.agent.tools.mac_vision import MacVisionTool


@pytest.mark.asyncio
async def test_mac_tool_requires_confirm_for_disruptive_actions():
    tool = MacTool(confirm_mode="require")
    # open_app is confirm-gated; should return before checking value
    result = await tool.execute("open_app")
    assert result == "Confirmation required: re-run with confirm=true."


@pytest.mark.asyncio
async def test_mac_vision_requires_confirm_for_capture():
    # Patch platform and framework availability for the test environment.
    mac_vision.platform.system = lambda: "Darwin"
    mac_vision.Quartz = object()
    mac_vision.Vision = object()
    mac_vision.NSURL = object()

    tool = MacVisionTool(confirm_mode="require")
    result = await tool.execute("capture_screen")
    assert result == "Confirmation required: re-run with confirm=true."
