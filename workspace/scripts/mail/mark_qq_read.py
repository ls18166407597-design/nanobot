#!/usr/bin/env python3
"""Compatibility wrapper: mail script moved to workspace/skills/mail/scripts."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "skills" / "mail" / "scripts" / "mark_qq_read.py"
    runpy.run_path(str(target), run_name="__main__")
