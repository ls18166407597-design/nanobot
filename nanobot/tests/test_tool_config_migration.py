from pathlib import Path

from typer.testing import CliRunner

from nanobot.cli.commands import app
from nanobot.utils.helpers import get_tool_config_path


def test_get_tool_config_path_prefers_new_dir(monkeypatch, tmp_path: Path):
    home = tmp_path / ".home"
    monkeypatch.setenv("NANOBOT_HOME", str(home))
    (home / "tool_configs").mkdir(parents=True, exist_ok=True)
    legacy = home / "gmail_config.json"
    modern = home / "tool_configs" / "gmail_config.json"
    legacy.write_text('{"email":"old"}', encoding="utf-8")
    modern.write_text('{"email":"new"}', encoding="utf-8")

    path = get_tool_config_path("gmail_config.json")
    assert path == modern


def test_get_tool_config_path_fallback_legacy(monkeypatch, tmp_path: Path):
    home = tmp_path / ".home"
    monkeypatch.setenv("NANOBOT_HOME", str(home))
    home.mkdir(parents=True, exist_ok=True)
    legacy = home / "gmail_config.json"
    legacy.write_text('{"email":"old"}', encoding="utf-8")

    path = get_tool_config_path("gmail_config.json")
    assert path == legacy


def test_get_tool_config_path_for_write_is_new(monkeypatch, tmp_path: Path):
    home = tmp_path / ".home"
    monkeypatch.setenv("NANOBOT_HOME", str(home))

    path = get_tool_config_path("gmail_config.json", for_write=True)
    assert path == home / "tool_configs" / "gmail_config.json"


def test_migrate_tool_configs_command_moves_files(monkeypatch, tmp_path: Path):
    home = tmp_path / ".home"
    monkeypatch.setenv("NANOBOT_HOME", str(home))
    home.mkdir(parents=True, exist_ok=True)
    (home / "github_config.json").write_text('{"token":"x"}', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["migrate-tool-configs"])
    assert result.exit_code == 0
    assert not (home / "github_config.json").exists()
    assert (home / "tool_configs" / "github_config.json").exists()


def test_migrate_tool_configs_dry_run(monkeypatch, tmp_path: Path):
    home = tmp_path / ".home"
    monkeypatch.setenv("NANOBOT_HOME", str(home))
    home.mkdir(parents=True, exist_ok=True)
    (home / "weather_config.json").write_text('{"key":"k"}', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["migrate-tool-configs", "--dry-run"])
    assert result.exit_code == 0
    assert (home / "weather_config.json").exists()
    assert not (home / "tool_configs" / "weather_config.json").exists()
