"""Async message queue for decoupled channel-agent communication."""

import asyncio
from typing import Awaitable, Callable

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    """

    def __init__(self, max_size: int = 100):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=max_size)
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=max_size)
        self._outbound_subscribers: dict[
            str, list[Callable[[OutboundMessage], Awaitable[None]]]
        ] = {}
        self._running = False

    async def publish_inbound(self, msg: InboundMessage, timeout: float = 5.0) -> bool:
        """
        Publish a message from a channel to the agent.
        Returns True if published, False if queue is full after timeout.
        """
        try:
            await asyncio.wait_for(self.inbound.put(msg), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.error(f"Inbound queue full, dropped message from {msg.channel}")
            return False

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage, timeout: float = 10.0) -> bool:
        """
        Publish a response from the agent to channels.
        Returns True if published, False if queue is full after timeout.
        """
        try:
            await asyncio.wait_for(self.outbound.put(msg), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.error(f"Outbound queue full, dropped message to {msg.channel}")
            return False

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    def subscribe_outbound(
        self, channel: str, callback: Callable[[OutboundMessage], Awaitable[None]]
    ) -> None:
        """Subscribe to outbound messages for a specific channel."""
        if channel not in self._outbound_subscribers:
            self._outbound_subscribers[channel] = []
        self._outbound_subscribers[channel].append(callback)

    async def dispatch_outbound(self) -> None:
        """
        Dispatch outbound messages to subscribed channels.
        Run this as a background task.
        """
        self._running = True
        while self._running:
            try:
                msg = await asyncio.wait_for(self.outbound.get(), timeout=1.0)
                subscribers = self._outbound_subscribers.get(msg.channel, [])
                for callback in subscribers:
                    # Execute callbacks as independent tasks to prevent a slow channel from blocking the bus
                    asyncio.create_task(self._safe_dispatch(callback, msg))
            except asyncio.TimeoutError:
                continue

    async def _safe_dispatch(self, callback: Callable[[OutboundMessage], Awaitable[None]], msg: OutboundMessage):
        """Helper to run callback with error handling and timeout."""
        try:
            # Add a generic high-level timeout for each channel's send operation (e.g. 60s)
            await asyncio.wait_for(callback(msg), timeout=60.0)
        except asyncio.TimeoutError:
            logger.error(f"Timeout dispatching message to {msg.channel} after 60s")
        except Exception as e:
            logger.error(f"Error dispatching message to {msg.channel}: {e}")

    def stop(self) -> None:
        """Stop the dispatcher loop."""
        self._running = False

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()
