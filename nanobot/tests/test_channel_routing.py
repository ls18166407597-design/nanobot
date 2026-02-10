import asyncio

import pytest

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.channels.manager import ChannelManager
from nanobot.config.schema import Config


class FakeChannel(BaseChannel):
    name = "fake"

    def __init__(self, config, bus):
        super().__init__(config, bus)
        self.sent = []

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        self.sent.append(msg)


@pytest.mark.asyncio
async def test_dispatch_outbound_routes_to_channel():
    bus = MessageBus()
    manager = ChannelManager(Config(), bus)
    fake = FakeChannel(config=Config().channels.telegram, bus=bus)
    manager.channels["fake"] = fake

    task = asyncio.create_task(manager._dispatch_outbound())
    try:
        msg = OutboundMessage(channel="fake", chat_id="1", content="hi")
        await bus.publish_outbound(msg)
        await asyncio.sleep(0.05)
        assert fake.sent and fake.sent[0].content == "hi"
    finally:
        task.cancel()
        await task


@pytest.mark.asyncio
async def test_base_channel_handle_message_respects_allow_list():
    bus = MessageBus()

    class AllowedChannel(FakeChannel):
        pass

    cfg = Config().channels.telegram
    cfg.allow_from = ["123"]
    ch = AllowedChannel(cfg, bus)

    await ch._handle_message(sender_id="999", chat_id="c", content="nope")
    assert bus.inbound_size == 0

    await ch._handle_message(sender_id="123", chat_id="c", content="ok")
    assert bus.inbound_size == 1
