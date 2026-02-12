from pathlib import Path

from nanobot.agent.memory import MemoryStore


def test_memory_search_supports_paraphrase_and_chinese_tokens(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(ws)

    store.write_long_term(
        "# 出行偏好\n"
        "用户常驻上海，周末常去浦东骑行。\n\n"
        "# 邮件习惯\n"
        "每天上午先看 Gmail 再看 QQ 邮箱。"
    )

    # Query wording differs from memory text; should still retrieve travel chunk.
    hits = store.search("周末在上海附近运动安排", top_k=2)
    assert hits
    assert "上海" in hits[0] or "浦东" in hits[0]


def test_memory_search_returns_empty_when_no_memory(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(ws)
    assert store.search("test query", top_k=3) == []
