from pathlib import Path

from nanobot.runtime.failures import list_recent_failures, record_failure, summarize_recent_failures


def test_runtime_failures_store_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path))
    record_failure("cron", "task_run", "任务失败", {"task": "demo"})
    record_failure("agent", "turn_error", "处理失败", {})
    items = list_recent_failures(limit=2)
    assert len(items) == 2
    assert items[0]["source"] in {"cron", "agent"}
    text = summarize_recent_failures(limit=2)
    assert "任务失败" in text or "处理失败" in text
