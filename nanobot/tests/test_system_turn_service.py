from pathlib import Path
import uuid

import pytest

from nanobot.agent.system_turn_service import SystemTurnService
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
    service = SystemTurnService(
        sessions=sessions,
        context=_FakeContext(),
        tools=_FakeTools(),
        turn_engine=_FakeTurnEngine(content),
        filter_reasoning=lambda s: s,
        is_silent_reply=lambda s: s == "[[NO_REPLY]]",
    )
    out = await service.process(msg)
    return out, sessions


@pytest.mark.asyncio
async def test_system_turn_service_routes_to_origin(tmp_path):
    chat_id = f"42-{uuid.uuid4().hex[:8]}"
    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="direct",
        content="hello",
        metadata={"origin": {"channel": "telegram", "chat_id": chat_id}},
    )
    out, sessions = await _run_service(tmp_path, msg, "ok")
    assert out is not None
    assert out.channel == "telegram"
    assert out.chat_id == chat_id
    session = sessions.get_or_create(f"telegram:{chat_id}")
    assert session.messages[-2]["role"] == "user"
    assert session.messages[-1]["role"] == "assistant"
    assert session.messages[-1]["content"] == "ok"


@pytest.mark.asyncio
async def test_system_turn_service_silent_reply_persists_only_user(tmp_path):
    chat_id = f"direct-{uuid.uuid4().hex[:8]}"
    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id=f"cli:{chat_id}",
        content="hello",
        metadata={},
    )
    out, sessions = await _run_service(tmp_path, msg, "[[NO_REPLY]]")
    assert out is None
    session = sessions.get_or_create(f"cli:{chat_id}")
    assert session.messages[-1]["role"] == "user"
    assert session.messages[-1]["content"].startswith("[System:")
