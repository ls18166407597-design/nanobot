"""Lightweight hook registry for lifecycle extensibility."""

import asyncio
import inspect
from collections import defaultdict
from typing import Any, Awaitable, Callable

from loguru import logger

HookCallback = Callable[[dict[str, Any]], Any] | Callable[[dict[str, Any]], Awaitable[Any]]


class HookRegistry:
    """Register and trigger lifecycle hooks without breaking the main flow."""

    def __init__(self, timeout_seconds: float = 0.2):
        self._hooks: dict[str, list[HookCallback]] = defaultdict(list)
        self.timeout_seconds = timeout_seconds

    def register_hook(self, event: str, callback: HookCallback) -> None:
        if not event or not callable(callback):
            return
        self._hooks[event].append(callback)

    async def trigger_hook(self, event: str, payload: dict[str, Any]) -> None:
        callbacks = self._hooks.get(event, [])
        if not callbacks:
            return

        for cb in callbacks:
            try:
                result = cb(payload)
                if inspect.isawaitable(result):
                    await asyncio.wait_for(result, timeout=self.timeout_seconds)
            except Exception as e:
                logger.warning(f"Hook '{event}' failed: {e}")
