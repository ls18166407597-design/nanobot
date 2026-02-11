from dataclasses import dataclass

from nanobot.bus.events import InboundMessage


@dataclass(frozen=True)
class SystemOrigin:
    """Resolved target origin and session key for a system message."""

    channel: str
    chat_id: str

    @property
    def session_key(self) -> str:
        return f"{self.channel}:{self.chat_id}"


def resolve_system_origin(msg: InboundMessage, default_channel: str = "cli") -> SystemOrigin:
    """
    Resolve where system-triggered outputs should be delivered and which session to use.

    Priority:
    1. `msg.metadata["origin"]` channel/chat_id
    2. `msg.chat_id` in `channel:chat_id` form
    3. default channel + raw chat_id
    """
    origin = msg.metadata.get("origin", {}) if msg.metadata else {}
    origin_channel = origin.get("channel")
    origin_chat_id = origin.get("chat_id")
    if origin_channel and origin_chat_id:
        return SystemOrigin(channel=str(origin_channel), chat_id=str(origin_chat_id))

    if ":" in msg.chat_id:
        channel, chat_id = msg.chat_id.split(":", 1)
        return SystemOrigin(channel=channel, chat_id=chat_id)

    return SystemOrigin(channel=default_channel, chat_id=msg.chat_id)
