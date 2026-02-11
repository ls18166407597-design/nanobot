from nanobot.agent.origin_resolver import resolve_system_origin
from nanobot.bus.events import InboundMessage


def test_resolve_system_origin_prefers_metadata_origin():
    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="direct",
        content="x",
        metadata={"origin": {"channel": "telegram", "chat_id": "100"}},
    )
    origin = resolve_system_origin(msg)
    assert origin.channel == "telegram"
    assert origin.chat_id == "100"
    assert origin.session_key == "telegram:100"


def test_resolve_system_origin_falls_back_to_prefixed_chat_id():
    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="discord:abc",
        content="x",
        metadata={},
    )
    origin = resolve_system_origin(msg)
    assert origin.channel == "discord"
    assert origin.chat_id == "abc"
    assert origin.session_key == "discord:abc"


def test_resolve_system_origin_uses_default_channel_with_raw_chat_id():
    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="direct",
        content="x",
        metadata={},
    )
    origin = resolve_system_origin(msg)
    assert origin.channel == "cli"
    assert origin.chat_id == "direct"
    assert origin.session_key == "cli:direct"
