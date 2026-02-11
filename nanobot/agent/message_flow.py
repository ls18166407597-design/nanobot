import time
from typing import Awaitable, Callable

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.process import CommandLane, CommandQueue


class MessageFlowCoordinator:
    """Coordinates inbound lane routing, busy notice, and error fallback routing."""

    def __init__(
        self,
        *,
        busy_notice_threshold: int,
        busy_notice_debounce_seconds: float,
        error_fallback_channel: str,
        error_fallback_chat_id: str,
        publish_outbound: Callable[[OutboundMessage], Awaitable[None]],
    ) -> None:
        self.busy_notice_threshold = busy_notice_threshold
        self.busy_notice_debounce_seconds = busy_notice_debounce_seconds
        self.error_fallback_channel = error_fallback_channel
        self.error_fallback_chat_id = error_fallback_chat_id
        self.publish_outbound = publish_outbound
        self._last_busy_notice_time = 0.0

    def lane_for(self, msg: InboundMessage) -> str:
        """System channel runs in background; all others run in main lane."""
        return CommandLane.BACKGROUND if msg.channel == "system" else CommandLane.MAIN

    async def maybe_send_busy_notice(self, msg: InboundMessage, lane: str) -> None:
        """Send debounced busy notice when the lane already has queued/active tasks."""
        if lane != CommandLane.MAIN:
            return

        lane_state = CommandQueue.get_lane(lane)
        queued_total = lane_state.active + len(lane_state.queue)
        if queued_total < self.busy_notice_threshold:
            return

        now = time.time()
        if now - self._last_busy_notice_time <= self.busy_notice_debounce_seconds:
            return

        self._last_busy_notice_time = now
        await self.publish_outbound(
            OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="老板，我正在全力处理您之前的指令，请稍等片刻，新指令已加入队列。",
            )
        )

    def build_error_outbound(self, msg: InboundMessage, error: Exception) -> OutboundMessage:
        """Route processing errors back to origin channel/chat, with robust fallback."""
        origin = msg.metadata.get("origin", {})
        if ":" in msg.chat_id:
            fallback_channel, fallback_chat_id = msg.chat_id.split(":", 1)
        elif msg.channel == "system":
            fallback_channel = self.error_fallback_channel
            fallback_chat_id = self.error_fallback_chat_id
        else:
            fallback_channel = msg.channel
            fallback_chat_id = msg.chat_id

        return OutboundMessage(
            channel=origin.get("channel") or fallback_channel,
            chat_id=origin.get("chat_id") or fallback_chat_id,
            content=f"抱歉，我在处理指令时遇到了错误: {str(error)}",
            trace_id=msg.trace_id,
        )
