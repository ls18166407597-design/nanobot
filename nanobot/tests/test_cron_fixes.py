from pathlib import Path

from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule


def test_cron_service_respects_default_timezone(tmp_path: Path):
    service = CronService(store_path=tmp_path / "jobs.json", default_tz="Asia/Shanghai")
    job = service.add_job(
        name="daily",
        schedule=CronSchedule(kind="cron", expr="0 9 * * *"),
        message="m",
    )
    assert job.state.next_run_at_ms is not None


def test_cron_service_accepts_task_run_payload_kind(tmp_path: Path):
    service = CronService(store_path=tmp_path / "jobs.json")
    job = service.add_job(
        name="task",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        message="[task_run] foo",
        payload_kind="task_run",
        task_name="foo",
    )
    assert job.payload.kind == "task_run"
    assert job.payload.task_name == "foo"
