from dataclasses import dataclass

import pytest

from nanobot.agent.message_flow import MessageFlowCoordinator
from nanobot.bus.events import InboundMessage
from nanobot.process import CommandLane, CommandQueue


@dataclass
class Sink:
    items: list

    async def publish(self, msg):
        self.items.append(msg)


def _coordinator(sink: Sink) -> MessageFlowCoordinator:
    return MessageFlowCoordinator(
        busy_notice_threshold=1,
        busy_notice_debounce_seconds=60,
        error_fallback_channel="cli",
        error_fallback_chat_id="direct",
        publish_outbound=sink.publish,
    )


def test_lane_for_system_and_main():
    sink = Sink(items=[])
    flow = _coordinator(sink)

    system_msg = InboundMessage(channel="system", sender_id="s", chat_id="direct", content="x")
    user_msg = InboundMessage(channel="telegram", sender_id="u", chat_id="123", content="x")

    assert flow.lane_for(system_msg) == CommandLane.BACKGROUND
    assert flow.lane_for(user_msg) == CommandLane.MAIN


def test_error_outbound_prefers_origin():
    sink = Sink(items=[])
    flow = _coordinator(sink)

    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="direct",
        content="x",
        metadata={"origin": {"channel": "telegram", "chat_id": "99"}},
        trace_id="t1",
    )
    out = flow.build_error_outbound(msg, RuntimeError("boom"))
    assert out.channel == "telegram"
    assert out.chat_id == "99"
    assert out.trace_id == "t1"
    assert "boom" in out.content


def test_error_outbound_uses_system_fallback_without_origin():
    sink = Sink(items=[])
    flow = _coordinator(sink)

    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="direct",
        content="x",
        metadata={},
    )
    out = flow.build_error_outbound(msg, RuntimeError("boom"))
    assert out.channel == "cli"
    assert out.chat_id == "direct"


@pytest.mark.asyncio
async def test_busy_notice_debounced():
    sink = Sink(items=[])
    flow = _coordinator(sink)

    lane = CommandQueue.get_lane(CommandLane.MAIN)
    old_active = lane.active
    old_queue = list(lane.queue)
    try:
        lane.active = 1
        lane.queue = []
        msg = InboundMessage(channel="telegram", sender_id="u", chat_id="123", content="x")

        await flow.maybe_send_busy_notice(msg, CommandLane.MAIN)
        await flow.maybe_send_busy_notice(msg, CommandLane.MAIN)
        assert len(sink.items) == 1
        assert "加入队列" in sink.items[0].content
    finally:
        lane.active = old_active
        lane.queue = old_queue
