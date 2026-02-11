from pathlib import Path

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.models import ModelRegistry, ProviderInfo
from nanobot.agent.provider_router import ProviderRouter
from nanobot.agent.tools.base import ToolResult
from nanobot.agent.turn_engine import TurnEngine
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.session.service import SessionService
from nanobot.utils.helpers import get_sessions_path, safe_filename


class _PrimaryFailProvider(LLMProvider):
    async def chat(self, *args, **kwargs):
        raise RuntimeError("primary down")

    def get_default_model(self) -> str:
        return "test-model"


class _SuccessProvider(LLMProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_model = "test-model"

    async def chat(self, *args, **kwargs):
        return LLMResponse(content="fallback ok")

    def get_default_model(self) -> str:
        return "test-model"


@pytest.mark.asyncio
async def test_provider_router_failover_to_registry(monkeypatch):
    primary = _PrimaryFailProvider(api_key="k1", api_base="http://primary")
    registry = ModelRegistry()
    registry.providers["fb"] = ProviderInfo(
        name="fb",
        base_url="http://fallback",
        api_key="k2",
        default_model="other-model",
        models=[],
    )

    fallback = _SuccessProvider(api_key="k2", api_base="http://fallback")

    from nanobot.providers import factory as provider_factory_mod

    def _fake_get_provider(*args, **kwargs):
        return fallback

    monkeypatch.setattr(provider_factory_mod.ProviderFactory, "get_provider", staticmethod(_fake_get_provider))

    pulses = []

    async def pulse(msg: str):
        pulses.append(msg)

    router = ProviderRouter(
        provider=primary,
        model="test-model",
        model_registry=registry,
        max_tokens=64,
        temperature=0.1,
        pulse_callback=pulse,
    )

    resp = await router.chat_with_failover(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert resp.content == "fallback ok"
    assert len(pulses) == 1


class _FakeContext:
    def add_assistant_message(self, messages, content, tool_calls):
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        return messages

    def add_tool_result(self, messages, tool_call_id, tool_name, result):
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result})
        return messages


class _FakeExecutor:
    async def execute(self, name, params):
        return ToolResult(success=True, output="ok")


@pytest.mark.asyncio
async def test_turn_engine_breaks_repeated_tool_loop():
    async def _chat_with_failover(messages, tools):
        return LLMResponse(
            content=None,
            tool_calls=[ToolCallRequest(id="call_1", name="echo", arguments={"q": "x"})],
        )

    async def _summarize(messages):
        return "summary"

    engine = TurnEngine(
        context=_FakeContext(),
        executor=_FakeExecutor(),
        model="test-model",
        max_iterations=6,
        get_tools_definitions=lambda: [],
        chat_with_failover=_chat_with_failover,
        parse_tool_calls_from_text=lambda text: [],
        summarize_messages=_summarize,
        self_correction_prompt="self-correct",
        loop_break_reply="loop-broken",
    )

    out = await engine.run(
        messages=[{"role": "system", "content": "s"}],
        trace_id="t1",
        parse_calls_from_text=False,
        include_severity=False,
        parallel_tool_exec=False,
        compact_after_tools=False,
    )
    assert out == "loop-broken"


class _OkProvider(LLMProvider):
    async def chat(self, *args, **kwargs):
        return LLMResponse(content="hello")

    def get_default_model(self) -> str:
        return "ok-model"


@pytest.mark.asyncio
async def test_process_direct_uses_session_key_override(tmp_path: Path):
    bus = MessageBus()
    loop = AgentLoop(bus=bus, provider=_OkProvider(), workspace=tmp_path)
    session_key = "custom:session-1"
    await loop.process_direct("ping", session_key=session_key, channel="cli", chat_id="direct")
    assert session_key in loop.sessions._cache


def test_inbound_message_session_key_override():
    from nanobot.bus.events import InboundMessage

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="123",
        content="hi",
        session_key_override="telegram:123#s1",
    )
    assert msg.session_key == "telegram:123#s1"


def test_inbound_message_metadata_session_key_is_ignored_without_override():
    from nanobot.bus.events import InboundMessage

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="123",
        content="hi",
        metadata={"session_key": "legacy:bad"},
    )
    assert msg.session_key == "telegram:123"


def test_session_service_use_session(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path / ".home"))
    svc = SessionService(channel_name="telegram")
    chat_id = "123"
    key = "telegram:123#sabc"
    sessions = get_sessions_path()
    sessions.mkdir(parents=True, exist_ok=True)
    file_path = sessions / f"{safe_filename(key.replace(':', '_'))}.jsonl"
    file_path.write_text('{"_type":"metadata","key":"telegram:123#sabc"}\n', encoding="utf-8")

    assert svc.use_session(chat_id, key) is True
    assert svc.get_active_session_key(chat_id) == key
    assert svc.use_session(chat_id, "telegram:999#x") is False
