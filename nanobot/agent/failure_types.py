"""Shared failure event types for agent/runtime error handling."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FailureSeverity(str, Enum):
    """Normalized severity levels across agent/cron/tool execution."""

    TRANSIENT = "transient"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class FailureEvent:
    """Canonical failure payload recorded by IncidentManager."""

    source: str
    category: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: FailureSeverity = FailureSeverity.ERROR
    retryable: bool = False
    fingerprint: str | None = None

    def resolved_fingerprint(self) -> str:
        if self.fingerprint:
            return self.fingerprint
        stable = {
            "source": self.source,
            "category": self.category,
            "summary": (self.summary or "").strip()[:120],
            "details": self._normalized_details(self.details),
        }
        raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _normalized_details(details: dict[str, Any]) -> dict[str, Any]:
        keep = ["tool", "error_type", "error_code", "job_id", "task_name", "reason"]
        normalized: dict[str, Any] = {}
        for k in keep:
            if k in details and details[k] is not None:
                normalized[k] = details[k]
        if not normalized:
            normalized = {"raw_keys": sorted(list(details.keys()))[:10]}
        return normalized

