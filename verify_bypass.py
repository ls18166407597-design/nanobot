import asyncio
from nanobot.agent.tools.browser import BrowserTool
from nanobot.config.loader import load_config

async def test_bypass():
    config = load_config()
    # Mocking browser tool with a fake proxy to test bypass logic
    tool = BrowserTool(proxy="http://127.0.0.1:7890")
    
    print("Testing Smart Bypass Logic...")
    
    urls = [
        "https://www.jd.com",
        "https://apple.com.cn",
        "https://www.google.com",
        "https://github.com"
    ]
    
    for url in urls:
        is_domestic = any(d in url.lower() for d in [".cn", "jd.com", "taobao.com", "tmall.com", "baidu.com", "apple.com.cn"])
        action = "BYPASS" if is_domestic else "PROXY"
        print(f"URL: {url:25} | Action: {action}")

    # Real execution test on JD.com (should be fast now)
    print("\nExecuting real browse on JD.com (Should bypass proxy)...")
    start = asyncio.get_event_loop().time()
    result = await tool.execute("browse", url="https://www.jd.com", wait_ms=1000)
    end = asyncio.get_event_loop().time()
    
    if "京东" in result or "JD.COM" in result.upper():
        print(f"SUCCESS: JD.com content captured in {end - start:.2f}s")
    else:
        print(f"FAILURE: Could not capture JD.com content. Result snippet: {result[:100]}")

if __name__ == "__main__":
    asyncio.run(test_bypass())
