import json
from pathlib import Path

from nanobot.session.manager import Session, SessionManager


def test_list_sessions_preserves_original_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path / ".home"))
    mgr = SessionManager(workspace=tmp_path)

    key = "telegram:group_chat_01"
    s = Session(key=key)
    s.add_message("user", "hi")
    s.add_message("assistant", "ok")
    mgr.save(s)

    sessions = mgr.list_sessions()
    assert sessions
    assert any(item["key"] == key for item in sessions)


def test_list_sessions_keeps_legacy_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path / ".home"))
    mgr = SessionManager(workspace=tmp_path)

    sessions_dir = Path(tmp_path / ".home" / "sessions")
    sessions_dir.mkdir(parents=True, exist_ok=True)
    legacy = sessions_dir / "telegram_direct.jsonl"
    metadata = {
        "_type": "metadata",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "metadata": {},
    }
    with open(legacy, "w", encoding="utf-8") as f:
        f.write(json.dumps(metadata) + "\n")

    sessions = mgr.list_sessions()
    assert sessions
    assert any(item["key"] == "telegram:direct" for item in sessions)
