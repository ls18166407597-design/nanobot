"""Persistent runtime failure queue for observability and agent awareness."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nanobot.config.loader import get_data_dir


@dataclass
class RuntimeFailure:
    ts: str
    source: str
    category: str
    summary: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "source": self.source,
            "category": self.category,
            "summary": self.summary,
            "details": self.details,
        }


def _store_path() -> Path:
    p = get_data_dir() / "runtime" / "failures.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> list[dict[str, Any]]:
    p = _store_path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def _save(items: list[dict[str, Any]]) -> None:
    p = _store_path()
    payload = {"items": items[-200:]}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def record_failure(source: str, category: str, summary: str, details: dict[str, Any] | None = None) -> None:
    items = _load()
    entry = RuntimeFailure(
        ts=datetime.now(timezone.utc).isoformat(),
        source=source,
        category=category,
        summary=(summary or "").strip()[:500],
        details=details or {},
    ).to_dict()
    items.append(entry)
    _save(items)


def list_recent_failures(limit: int = 10) -> list[dict[str, Any]]:
    items = _load()
    if limit <= 0:
        return []
    return list(reversed(items[-limit:]))


def summarize_recent_failures(limit: int = 5) -> str:
    items = list_recent_failures(limit=limit)
    if not items:
        return "近期无运行失败事件。"
    lines = []
    for i, it in enumerate(items, start=1):
        ts = str(it.get("ts", ""))[:19].replace("T", " ")
        lines.append(
            f"{i}. [{ts}] {it.get('source', '-')}/{it.get('category', '-')}: {it.get('summary', '')}"
        )
    return "\n".join(lines)

