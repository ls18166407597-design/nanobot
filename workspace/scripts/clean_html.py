#!/usr/bin/env python3
"""Compatibility wrapper: html-cleanup script moved to workspace/skills/html-cleanup/scripts."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "skills" / "html-cleanup" / "scripts" / "clean_html.py"
    runpy.run_path(str(target), run_name="__main__")
