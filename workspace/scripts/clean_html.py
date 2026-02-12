#!/usr/bin/env python3
"""Clean HTML into compact plain text from stdin."""

from __future__ import annotations

import html as html_lib
import re
import sys

_COMMENTS_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", flags=re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_html(html_text: str) -> str:
    """Return plain text extracted from HTML."""
    text = _COMMENTS_RE.sub("", html_text)
    text = _SCRIPT_STYLE_RE.sub("", text)
    text = _TAG_RE.sub(" ", text)
    text = html_lib.unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def main() -> int:
    content = sys.stdin.read()
    if not content:
        return 0
    print(clean_html(content))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
