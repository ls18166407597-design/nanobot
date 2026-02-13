from pathlib import Path

from nanobot.agent.task_manager import TaskManager


def test_task_manager_state_machine_roundtrip(tmp_path: Path):
    storage = tmp_path / "tasks.json"
    mgr = TaskManager(storage)
    mgr.create(name="demo", description="d", command="echo ok")

    assert mgr.mark_running("demo") is True
    assert mgr.mark_result("demo", success=False, error="boom", duration_ms=12) is True
    assert mgr.mark_running("demo", retry=True) is True
    assert mgr.mark_result("demo", success=True, duration_ms=8) is True

    reloaded = TaskManager(storage)
    task = reloaded.get("demo")
    assert task is not None
    assert task.status == "completed"
    assert task.run_count == 2
    assert task.retry_count == 1
    assert task.failure_count == 1
    assert task.success_count == 1
    assert task.last_error is None

