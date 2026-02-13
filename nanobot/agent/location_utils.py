"""Shared location parsing and fallback utilities for tools."""

from __future__ import annotations

import re
from typing import Any


_TRAILING_FINE_GRAIN = (
    "街道",
    "乡",
    "镇",
    "村",
    "社区",
    "新区",
    "开发区",
    "工业园",
)

_ADMIN_SUFFIXES = ("省", "市", "自治区", "特别行政区", "地区", "盟", "州", "区", "县")


def normalize_location_text(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"\s+", "", s)
    for token in _ADMIN_SUFFIXES:
        s = s.replace(token, "")
    return s


def location_query_variants(query: str, max_steps: int = 4) -> list[str]:
    """
    Produce coarse-grained query variants from specific to broad.

    Example:
      重庆市忠县汝溪镇 -> [重庆市忠县汝溪镇, 重庆市忠县, 重庆市, 忠县汝溪镇, 忠县, 重庆]
    """
    q = (query or "").strip()
    if not q:
        return []

    variants: list[str] = []

    def _push(v: str) -> None:
        v = v.strip()
        if v and v not in variants:
            variants.append(v)

    _push(q)

    # Path 1: strip trailing fine-grained suffixes iteratively.
    cur = q
    for _ in range(max_steps):
        changed = False
        for suffix in _TRAILING_FINE_GRAIN:
            if cur.endswith(suffix):
                cur = cur[: -len(suffix)].strip()
                if cur:
                    _push(cur)
                changed = True
                break
        if not changed:
            # Trim one trailing token chunk (Chinese administrative unit-like segment).
            m = re.match(r"^(.+?)([^省市区县州盟地区特别行政区自治区]{1,8})$", cur)
            if m and len(m.group(1)) >= 2:
                cur = m.group(1).strip()
                _push(cur)
            break

    # Path 2: split administrative chain.
    parts = re.split(r"(省|市|自治区|特别行政区|地区|盟|州|区|县)", q)
    chain: list[str] = []
    for i in range(0, len(parts) - 1, 2):
        chain.append((parts[i] + parts[i + 1]).strip())
    if chain:
        joined = ""
        for seg in chain:
            joined += seg
            _push(joined)
        # Also push tail segments (e.g. 忠县)
        for seg in chain:
            _push(seg)

    # Coarse-only variants without suffixes.
    norm = normalize_location_text(q)
    if norm:
        _push(norm)

    return variants


def score_geo_candidate(query: str, item: dict[str, Any]) -> int:
    q = normalize_location_text(query)
    name = normalize_location_text(str(item.get("name", "")))
    adm2 = normalize_location_text(str(item.get("adm2", "")))
    adm1 = normalize_location_text(str(item.get("adm1", "")))

    score = 0
    if name and name in q:
        score += 120
    if adm2 and adm2 in q:
        score += 90
    if adm1 and adm1 in q:
        score += 60
    if name and adm2 and f"{adm2}{name}" in q:
        score += 140
    return score

