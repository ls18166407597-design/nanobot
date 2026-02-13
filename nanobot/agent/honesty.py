import re
from typing import Any

def audit_and_mark_hallucinations(
    content: str, used_tools: list[str], all_tools_meta: list[dict[str, Any]]
) -> tuple[str, bool]:
    """
    Detect and mark tool execution hallucinations using strikethroughs.
    Returns (processed_content, hallucination_detected_boolean).
    Shared by UserTurnService and SystemTurnService.
    """
    used = set(used_tools or [])
    hallucination_detected = False

    # Build dynamic tool alias map
    # e.g., "amap" -> ["amap", "高德", "地图"]
    tool_alias_map: dict[str, set[str]] = {}
    for meta in all_tools_meta:
        name = str(meta.get("name", ""))
        desc = str(meta.get("description", ""))
        aliases = {name.lower()}
        # Extract common business names from description (CJK only)
        cjk_names = re.findall(r"[\u4e00-\u9fff]{2,}", desc)
        for cjk in cjk_names:
            if cjk not in ("工具", "封装", "插件", "使用", "能力", "查看"):
                aliases.add(cjk)
        tool_alias_map[name] = aliases

    # Specific well-known aliases for core tools
    core_overrides = {
        "browser": {"浏览器", "网页", "上网"},
        "tavily": {"搜索", "联网", "Tavily"},
        "github": {"GitHub", "仓库", "代码仓"},
        "train_ticket": {"12306", "火车票", "买票"},
    }
    for k, v in core_overrides.items():
        if k in tool_alias_map:
            tool_alias_map[k].update(v)

    claim_markers = ("我用", "使用了", "调用了", "测试了", "刚才", "本次", "通过")
    lines = content.splitlines()
    processed_lines: list[str] = []

    for line in lines:
        should_mark = False
        found_tool_name = ""

        for tool_name, aliases in tool_alias_map.items():
            if tool_name in used or f"mcp:{tool_name}" in used:
                continue

            if any(a in line for a in aliases) and any(m in line for m in claim_markers):
                should_mark = True
                found_tool_name = tool_name
                break

        if should_mark:
            hallucination_detected = True
            # Format: ~~original line~~ [审计：记录中未见 xxx 相关操作]
            processed_lines.append(f"~~{line.strip()}~~ [审计：记录中未见 {found_tool_name} 相关操作]")
        else:
            processed_lines.append(line)

    return "\n".join(processed_lines).strip(), hallucination_detected
