from pathlib import Path

from nanobot.agent.file_write_policy import FileWritePolicy


def test_read_only_path_blocked(tmp_path: Path):
    root = tmp_path / "repo"
    p = root / "workspace" / "IDENTITY.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    policy = FileWritePolicy(
        project_root=root,
        read_only_patterns=["workspace/IDENTITY.md"],
        controlled_patterns=[],
    )
    ok, reason = policy.check_write(p, confirm=False, change_note="")
    assert ok is False
    assert "只读" in reason


def test_controlled_requires_confirm_and_note(tmp_path: Path):
    root = tmp_path / "repo"
    p = root / "docs" / "A.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    policy = FileWritePolicy(
        project_root=root,
        read_only_patterns=[],
        controlled_patterns=["docs/*.md"],
    )
    ok1, _ = policy.check_write(p, confirm=False, change_note="")
    ok2, _ = policy.check_write(p, confirm=True, change_note="")
    ok3, _ = policy.check_write(p, confirm=True, change_note="doc update")
    assert ok1 is False
    assert ok2 is False
    assert ok3 is True

