from pathlib import Path

from nanobot.utils.helpers import get_tool_config_path


def test_get_tool_config_path_is_new_dir(monkeypatch, tmp_path: Path):
    home = tmp_path / ".home"
    monkeypatch.setenv("NANOBOT_HOME", str(home))
    path = get_tool_config_path("gmail_config.json")
    assert path == home / "tool_configs" / "gmail_config.json"


def test_get_tool_config_path_ignores_old_root_file(monkeypatch, tmp_path: Path):
    home = tmp_path / ".home"
    monkeypatch.setenv("NANOBOT_HOME", str(home))
    home.mkdir(parents=True, exist_ok=True)
    (home / "gmail_config.json").write_text('{"email":"old"}', encoding="utf-8")

    path = get_tool_config_path("gmail_config.json")
    assert path == home / "tool_configs" / "gmail_config.json"


def test_get_tool_config_path_for_write_is_new(monkeypatch, tmp_path: Path):
    home = tmp_path / ".home"
    monkeypatch.setenv("NANOBOT_HOME", str(home))

    path = get_tool_config_path("gmail_config.json", for_write=True)
    assert path == home / "tool_configs" / "gmail_config.json"
