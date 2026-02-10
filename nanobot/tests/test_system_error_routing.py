import asyncio
from pathlib import Path

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.bus.events import InboundMessage
from nanobot.providers.base import LLMProvider, LLMResponse


class FakeProvider(LLMProvider):
    async def chat(self, *args, **kwargs):
        return LLMResponse(content="ok")

    def get_default_model(self) -> str:
        return "fake-model"


class ExplodingAgent(AgentLoop):
    async def _inner_process_message(self, msg):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_system_error_routes_to_origin():
    bus = MessageBus()
    agent = ExplodingAgent(
        bus=bus,
        provider=FakeProvider(),
        workspace=Path("/Users/liusong/Downloads/nanobot/workspace"),
    )

    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="direct",
        content="test",
        metadata={"origin": {"channel": "telegram", "chat_id": "12345"}},
    )

    task = asyncio.create_task(agent._process_message_wrapper(msg))
    out = await bus.consume_outbound()
    await task

    assert out.channel == "telegram"
    assert out.chat_id == "12345"
    assert "boom" in out.content


@pytest.mark.asyncio
async def test_system_error_routes_to_cli_when_no_origin_or_prefix():
    bus = MessageBus()
    agent = ExplodingAgent(
        bus=bus,
        provider=FakeProvider(),
        workspace=Path("/Users/liusong/Downloads/nanobot/workspace"),
    )

    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="direct",
        content="test",
        metadata={},
    )

    task = asyncio.create_task(agent._process_message_wrapper(msg))
    out = await bus.consume_outbound()
    await task

    assert out.channel == "cli"
    assert out.chat_id == "direct"
    assert "boom" in out.content
