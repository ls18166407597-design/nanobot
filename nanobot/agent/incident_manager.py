"""Incident manager for failure classification, dedupe and escalation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from loguru import logger

from nanobot.agent.failure_types import FailureEvent, FailureSeverity
from nanobot.runtime.failures import record_failure


@dataclass
class IncidentDecision:
    """Decision returned by incident handling."""

    fingerprint: str
    count_in_window: int
    should_notify_user: bool
    should_escalate: bool


class IncidentManager:
    """
    Centralized runtime failure handler.

    Rules:
    - Always persist failures for audit/diagnostics.
    - De-duplicate by fingerprint in a time window.
    - Suppress user-facing noise for low-frequency transient failures.
    """

    def __init__(
        self,
        *,
        dedupe_window_seconds: int = 1800,
        escalate_threshold: int = 3,
        on_decision: Callable[[FailureEvent, IncidentDecision], None] | None = None,
    ):
        self.dedupe_window_seconds = max(60, int(dedupe_window_seconds))
        self.escalate_threshold = max(2, int(escalate_threshold))
        self.on_decision = on_decision
        self._seen: dict[str, dict[str, Any]] = {}

    def report(self, event: FailureEvent) -> IncidentDecision:
        now = time.time()
        self._prune(now)
        fp = event.resolved_fingerprint()
        row = self._seen.get(fp)
        if row is None:
            row = {"first": now, "last": now, "count": 0}
            self._seen[fp] = row
        row["last"] = now
        row["count"] = int(row.get("count", 0)) + 1
        count = int(row["count"])

        record_failure(
            source=event.source,
            category=event.category,
            summary=event.summary,
            details={
                **event.details,
                "severity": event.severity.value,
                "retryable": event.retryable,
                "fingerprint": fp,
                "count_in_window": count,
            },
        )

        # 用户通知策略：只在同类故障持续出现时通知，避免单次波动打扰。
        severe = event.severity in {FailureSeverity.ERROR, FailureSeverity.CRITICAL}
        should_escalate = severe and count >= self.escalate_threshold
        should_notify_user = should_escalate

        logger.warning(
            "Incident: source={} category={} severity={} retryable={} fp={} count={}",
            event.source,
            event.category,
            event.severity.value,
            event.retryable,
            fp,
            count,
        )
        decision = IncidentDecision(
            fingerprint=fp,
            count_in_window=count,
            should_notify_user=should_notify_user,
            should_escalate=should_escalate,
        )
        if self.on_decision is not None:
            try:
                self.on_decision(event, decision)
            except Exception as e:
                logger.debug(f"IncidentManager on_decision callback ignored error: {e}")
        return decision

    def _prune(self, now: float) -> None:
        cutoff = now - self.dedupe_window_seconds
        stale = [fp for fp, row in self._seen.items() if float(row.get("last", 0.0)) < cutoff]
        for fp in stale:
            self._seen.pop(fp, None)
