import json
from pathlib import Path

from nanobot.cli.commands import _collect_health_snapshot
from nanobot.cli.runtime_commands import collect_tool_health_snapshot
from nanobot.config.loader import get_config_path, get_data_dir, load_config, save_config
from nanobot.config.schema import Config


def _setup_tmp_home(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / ".home"
    monkeypatch.setenv("NANOBOT_HOME", str(home))
    data_dir = get_data_dir()
    config_path = get_config_path()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir, config_path


def test_collect_health_snapshot_gateway_running(monkeypatch, tmp_path: Path):
    data_dir, config_path = _setup_tmp_home(monkeypatch, tmp_path)
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    cfg = Config()
    cfg.agents.defaults.workspace = str(ws)
    save_config(cfg, config_path=config_path)
    config = load_config(config_path=config_path)

    pid_file = data_dir / "gateway.pid"
    pid_file.write_text(str(1), encoding="utf-8")
    audit_path = data_dir / "audit.log"
    audit_path.write_text(
        json.dumps({"type": "tool_end", "status": "error"}) + "\n", encoding="utf-8"
    )

    monkeypatch.setattr("os.kill", lambda pid, sig: None)
    snap = _collect_health_snapshot(config=config, data_dir=data_dir, config_path=config_path)
    assert snap["config_exists"] is True
    assert snap["workspace_exists"] is True
    assert snap["gateway_running"] is True
    assert snap["pid"] == 1
    assert snap["stale_pid"] is False
    assert snap["recent_errors"] == 1


def test_collect_health_snapshot_stale_pid(monkeypatch, tmp_path: Path):
    data_dir, config_path = _setup_tmp_home(monkeypatch, tmp_path)
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    cfg = Config()
    cfg.agents.defaults.workspace = str(ws)
    save_config(cfg, config_path=config_path)
    config = load_config(config_path=config_path)

    pid_file = data_dir / "gateway.pid"
    pid_file.write_text("99999", encoding="utf-8")

    def _raise_oserror(_pid, _sig):
        raise OSError("no process")

    monkeypatch.setattr("os.kill", _raise_oserror)
    snap = _collect_health_snapshot(config=config, data_dir=data_dir, config_path=config_path)
    assert snap["gateway_running"] is False
    assert snap["stale_pid"] is True


def test_collect_tool_health_snapshot(monkeypatch, tmp_path: Path):
    data_dir, _ = _setup_tmp_home(monkeypatch, tmp_path)
    audit_path = data_dir / "audit.log"
    audit_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "tool_end", "tool": "tavily", "status": "ok", "duration_s": 0.5}),
                json.dumps({"type": "tool_end", "tool": "tavily", "status": "timeout", "duration_s": 1.2}),
                json.dumps({"type": "tool_end", "tool": "browser", "status": "error", "duration_s": 2.0}),
                json.dumps({"type": "turn_end", "has_content": False}),
                json.dumps({"type": "turn_end", "has_content": True}),
            ]
        ),
        encoding="utf-8",
    )

    snap = collect_tool_health_snapshot(data_dir=data_dir, lines=100)
    assert snap["summary"]["total_calls"] == 3
    assert snap["summary"]["failure_rate"] == 0.6667
    assert snap["summary"]["timeout_rate"] == 0.3333
    assert snap["summary"]["empty_reply_rate"] == 0.5
    assert snap["tools"]["tavily"]["calls"] == 2
    assert snap["tools"]["tavily"]["timeout_rate"] == 0.5
