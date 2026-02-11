import inspect

import pytest

from nanobot.agent.provider_router import ProviderRouter
from nanobot.agent.tools.base import ToolResult
from nanobot.agent.turn_engine import TurnEngine
from nanobot.bus.events import InboundMessage
from nanobot.providers.base import LLMProvider, LLMResponse


class _AlwaysFailProvider(LLMProvider):
    async def chat(self, *args, **kwargs):
        raise RuntimeError("down")

    def get_default_model(self) -> str:
        return "m"


@pytest.mark.asyncio
async def test_provider_router_returns_error_response_when_all_fail():
    router = ProviderRouter(
        provider=_AlwaysFailProvider(api_key="k", api_base="http://x"),
        model="m",
        model_registry=None,
        max_tokens=32,
        temperature=0.1,
        pulse_callback=None,
    )
    resp = await router.chat_with_failover(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert isinstance(resp, LLMResponse)
    assert resp.finish_reason == "error"
    assert resp.content and "所有可用的大脑" in resp.content


def test_inbound_message_session_key_contract():
    msg_default = InboundMessage(channel="telegram", sender_id="u", chat_id="1", content="x")
    assert msg_default.session_key == "telegram:1"

    msg_override = InboundMessage(
        channel="telegram",
        sender_id="u",
        chat_id="1",
        content="x",
        session_key_override="telegram:1#s1",
    )
    assert msg_override.session_key == "telegram:1#s1"


def test_toolresult_contract_shape():
    res = ToolResult(success=True, output="ok")
    assert hasattr(res, "success")
    assert hasattr(res, "output")
    assert hasattr(res, "remedy")
    assert hasattr(res, "severity")
    assert hasattr(res, "should_retry")
    assert hasattr(res, "requires_user_confirmation")


def test_turn_engine_run_signature_contract():
    sig = inspect.signature(TurnEngine.run)
    params = list(sig.parameters.keys())
    expected = [
        "self",
        "messages",
        "trace_id",
        "parse_calls_from_text",
        "include_severity",
        "parallel_tool_exec",
        "compact_after_tools",
    ]
    assert params == expected
