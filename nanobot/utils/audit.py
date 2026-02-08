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
    """Append a single JSON event to the audit log."""
    try:
        path = _audit_path()
        # logger.debug(f"Logging audit event to {path}")
        payload = dict(event)
        payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug(f"Audit log failed: {e}")
