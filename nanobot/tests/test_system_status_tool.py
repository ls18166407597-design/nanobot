from pathlib import Path

import pytest

from nanobot.agent.tools.system_status import SystemStatusTool


@pytest.mark.asyncio
async def test_system_status_reset_runtime_requires_confirm(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path))
    tool = SystemStatusTool()
    res = await tool.execute(action="reset_runtime", confirm=False)
    assert res.success is False
    assert "confirm=true" in res.remedy


@pytest.mark.asyncio
async def test_system_status_reset_runtime_keeps_tasks_by_default(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path))
    data = tmp_path
    (data / "sessions").mkdir(parents=True, exist_ok=True)
    (data / "runtime").mkdir(parents=True, exist_ok=True)
    (data / "sessions" / "a.jsonl").write_text("{}", encoding="utf-8")
    (data / "runtime" / "failures.json").write_text("{}", encoding="utf-8")
    (data / "gateway.log").write_text("x", encoding="utf-8")
    (data / "audit.log").write_text("x", encoding="utf-8")
    (data / "tasks.json").write_text("{}", encoding="utf-8")

    tool = SystemStatusTool()
    res = await tool.execute(action="reset_runtime", confirm=True)
    assert res.success is True
    assert (data / "tasks.json").exists()
    assert not (data / "sessions" / "a.jsonl").exists()
    assert not (data / "runtime" / "failures.json").exists()
    assert not (data / "gateway.log").exists()
    assert not (data / "audit.log").exists()

