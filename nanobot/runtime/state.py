"""Runtime state maintenance helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nanobot.config.loader import get_data_dir


def reset_runtime_state(
    *,
    clear_sessions: bool = True,
    clear_failures: bool = True,
    clear_logs: bool = True,
    preserve_tasks: bool = True,
) -> dict[str, Any]:
    """
    Clear runtime artifacts for clean re-testing while keeping core config.

    Returns summary counts for reporting.
    """
    data_dir: Path = get_data_dir()
    summary = {
        "sessions_removed": 0,
        "logs_removed": 0,
        "failures_removed": 0,
        "tasks_preserved": bool(preserve_tasks),
    }

    if clear_sessions:
        sessions_dir = data_dir / "sessions"
        if sessions_dir.exists():
            for p in sessions_dir.glob("*.jsonl"):
                try:
                    p.unlink()
                    summary["sessions_removed"] += 1
                except Exception:
                    pass

    if clear_failures:
        failures = data_dir / "runtime" / "failures.json"
        if failures.exists():
            try:
                failures.unlink()
                summary["failures_removed"] = 1
            except Exception:
                pass

    if clear_logs:
        for p in (data_dir / "gateway.log", data_dir / "audit.log"):
            if p.exists():
                try:
                    p.unlink()
                    summary["logs_removed"] += 1
                except Exception:
                    pass

    if not preserve_tasks:
        tasks = data_dir / "tasks.json"
        if tasks.exists():
            try:
                tasks.unlink()
                summary["tasks_preserved"] = False
            except Exception:
                pass

    return summary

