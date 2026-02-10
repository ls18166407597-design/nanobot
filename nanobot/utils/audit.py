"""Lightweight audit logging for tool executions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.config.loader import get_data_dir


def _audit_path() -> Path:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "audit.log"


def log_event(event: dict[str, Any]) -> None:
    """Append a single JSON event to the audit log with immediate flushing."""
    import os
    try:
        path = _audit_path()
        payload = dict(event)
        payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
        if payload.get("type") in {"tool_start", "tool_end"}:
            payload.setdefault("trace_id", None)
            payload.setdefault("tool", None)
            payload.setdefault("tool_call_id", None)
            payload.setdefault("status", None)
            payload.setdefault("duration_s", None)
            payload.setdefault("result_len", None)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        logger.debug(f"Audit log failed: {e}")
