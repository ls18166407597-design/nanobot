from pathlib import Path

import pytest

from nanobot.agent.task_manager import TaskManager
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.task import TaskTool


@pytest.mark.asyncio
async def test_task_update_accepts_new_command_alias(tmp_path: Path):
    tasks_path = tmp_path / "tasks.json"
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    script = workspace / "demo.py"
    script.write_text("print('ok')\n", encoding="utf-8")

    manager = TaskManager(tasks_path)
    exec_tool = ExecTool(timeout=3, working_dir=str(workspace))
    tool = TaskTool(task_manager=manager, exec_tool=exec_tool)

    created = await tool.execute(
        action="create",
        name="demo",
        description="demo",
        command="python3 demo.py",
    )
    assert created.success

    updated = await tool.execute(
        action="update",
        name="demo",
        new_command="python3 demo.py --flag",
    )
    assert updated.success
    task = manager.get("demo")
    assert task is not None
    assert "--flag" in task.command


@pytest.mark.asyncio
async def test_task_preflight_resolves_relative_script_from_exec_working_dir(tmp_path: Path):
    tasks_path = tmp_path / "tasks.json"
    workspace = tmp_path / "workspace"
    scripts = workspace / "scripts" / "telegram"
    scripts.mkdir(parents=True, exist_ok=True)
    script = scripts / "tg_checkin_task_blind.py"
    script.write_text("print('ok')\n", encoding="utf-8")

    manager = TaskManager(tasks_path)
    exec_tool = ExecTool(timeout=3, working_dir=str(workspace))
    tool = TaskTool(task_manager=manager, exec_tool=exec_tool)

    created = await tool.execute(
        action="create",
        name="tg",
        description="tg",
        command="python3 scripts/telegram/tg_checkin_task_blind.py",
    )
    assert created.success

