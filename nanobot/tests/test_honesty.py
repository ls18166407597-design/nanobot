import pytest
from nanobot.agent.honesty import audit_and_mark_hallucinations

def test_hallucination_detection_strikethrough():
    # 模拟工具元数据
    all_tools_meta = [
        {"name": "github", "description": "GitHub 仓库操作工具"},
        {"name": "amap", "description": "高德地图搜索工具"},
        {"name": "browser", "description": "网页浏览器工具"}
    ]
    
    # 场景 1: AI 撒谎说查了 GitHub，但 used_tools 为空
    content = "我刚才使用了 GitHub 搜索了 nanobot 仓库。\n确实存在这个项目。"
    used_tools = ["weather"] # 实际只用了天气
    
    processed, detected = audit_and_mark_hallucinations(content, used_tools, all_tools_meta)
    
    assert detected is True
    # 检查删除线标记
    assert "~~我刚才使用了 GitHub 搜索了 nanobot 仓库。~~" in processed
    assert "[审计：记录中未见 github 相关操作]" in processed
    # 正常行不应该被划掉
    assert "确实存在这个项目。" in processed
    assert "~~确实存在这个项目。~~" not in processed

def test_dynamic_alias_extraction():
    # 测试动态词库提取：从描述中提取中文特征词
    all_tools_meta = [
        {"name": "train_ticket", "description": "12306 火车票查询插件"}
    ]
    
    # AI 提及了“12306”和“火车票”
    content = "我用 12306 查了一下火车票，目前还有余票。"
    used_tools = []
    
    processed, detected = audit_and_mark_hallucinations(content, used_tools, all_tools_meta)
    
    assert detected is True
    assert "~~我用 12306 查了一下火车票，目前还有余票。~~" in processed
    assert "train_ticket" in processed

def test_no_hallucination_when_tool_actually_used():
    all_tools_meta = [
        {"name": "amap", "description": "高德地图"}
    ]
    
    content = "由于我刚才通过 高德 查到了路线，现在告诉你结果。"
    used_tools = ["amap"]
    
    processed, detected = audit_and_mark_hallucinations(content, used_tools, all_tools_meta)
    
    assert detected is False
    assert "~~" not in processed
    assert "高德" in processed

def test_mcp_format_compatibility():
    # 测试对 mcp:xxx 格式的兼容性
    all_tools_meta = [
        {"name": "puppeteer", "description": "浏览器内核控制"}
    ]
    
    content = "我刚才测试了 浏览器 发现网页打不开。"
    used_tools = ["mcp:puppeteer"] # 内核记录通常带前缀
    
    processed, detected = audit_and_mark_hallucinations(content, used_tools, all_tools_meta)
    
    assert detected is False
    assert "~~" not in processed
