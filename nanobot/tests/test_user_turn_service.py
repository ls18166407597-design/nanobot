import uuid
from pathlib import Path

import pytest

from nanobot.agent.user_turn_service import UserTurnService
from nanobot.bus.events import InboundMessage
from nanobot.session.manager import SessionManager


class _FakeContext:
    def build_messages(self, **kwargs):
        return [{"role": "user", "content": kwargs["current_message"]}]


class _FakeTools:
    def get(self, _name):
        return None


class _FakeTurnEngine:
    def __init__(self, content):
        self.content = content

    async def run(self, **_kwargs):
        return self.content


async def _run_service(tmp_path: Path, msg: InboundMessage, content: str):
    sessions = SessionManager(tmp_path)

    async def _compact(_session):
        return None

    service = UserTurnService(
        sessions=sessions,
        context=_FakeContext(),
        tools=_FakeTools(),
        turn_engine=_FakeTurnEngine(content),
        compact_history=_compact,
        filter_reasoning=lambda s: s,
        is_silent_reply=lambda s: s == "[[NO_REPLY]]",
    )
    out = await service.process(msg)
    return out, sessions


@pytest.mark.asyncio
async def test_user_turn_service_persists_user_and_assistant(tmp_path):
    chat_id = f"u-{uuid.uuid4().hex[:8]}"
    msg = InboundMessage(
        channel="telegram",
        sender_id="user1",
        chat_id=chat_id,
        content="hello",
        metadata={},
        trace_id="trace-1",
    )
    out, sessions = await _run_service(tmp_path, msg, "ok")
    assert out is not None
    assert out.channel == "telegram"
    assert out.chat_id == chat_id
    assert out.trace_id == "trace-1"
    session = sessions.get_or_create(f"telegram:{chat_id}")
    assert session.messages[-2]["role"] == "user"
    assert session.messages[-1]["role"] == "assistant"
    assert session.messages[-1]["content"] == "ok"


@pytest.mark.asyncio
async def test_user_turn_service_silent_reply_persists_only_user(tmp_path):
    chat_id = f"u-{uuid.uuid4().hex[:8]}"
    msg = InboundMessage(
        channel="cli",
        sender_id="user1",
        chat_id=chat_id,
        content="hello",
        metadata={},
    )
    out, sessions = await _run_service(tmp_path, msg, "[[NO_REPLY]]")
    assert out is None
    session = sessions.get_or_create(f"cli:{chat_id}")
    assert session.messages[-1]["role"] == "user"
    assert session.messages[-1]["content"] == "hello"
