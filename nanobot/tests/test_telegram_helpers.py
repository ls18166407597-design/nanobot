from pathlib import Path

import pytest

from nanobot.channels.telegram_format import markdown_to_telegram_html, split_message
from nanobot.channels.telegram_media import build_message_content


def test_markdown_to_telegram_html_basic():
    text = "**B** _i_ [x](https://example.com) `code`"
    out = markdown_to_telegram_html(text)
    assert "<b>B</b>" in out
    assert "<i>i</i>" in out
    assert '<a href="https://example.com">x</a>' in out
    assert "<code>code</code>" in out


def test_split_message_respects_limit():
    text = "a\n" * 5000
    parts = split_message(text, limit=200)
    assert len(parts) > 1
    assert all(len(p) <= 200 for p in parts)


class _FakeFile:
    def __init__(self, payload: bytes = b"x"):
        self.payload = payload

    async def download_to_drive(self, path: str) -> None:
        Path(path).write_bytes(self.payload)


class _FakeBot:
    async def get_file(self, file_id: str):
        return _FakeFile(payload=b"hello")


class _FakeApp:
    def __init__(self):
        self.bot = _FakeBot()


class _Obj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.asyncio
async def test_build_message_content_text_only():
    msg = _Obj(text="hi", caption=None, photo=None, voice=None, audio=None, document=None)
    content, media = await build_message_content(msg, app=None, groq_api_key="")
    assert content == "hi"
    assert media == []


@pytest.mark.asyncio
async def test_build_message_content_with_document_download(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NANOBOT_HOME", str(tmp_path / ".home"))
    doc = _Obj(file_id="abc123", mime_type="application/pdf")
    msg = _Obj(text=None, caption=None, photo=None, voice=None, audio=None, document=doc)
    app = _FakeApp()

    content, media = await build_message_content(msg, app=app, groq_api_key="")
    assert len(media) == 1
    saved = Path(media[0])
    assert saved.exists()
    assert "[file:" in content
