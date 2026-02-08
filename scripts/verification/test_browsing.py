import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from nanobot.agent.tools.browser import BrowserTool
from nanobot.config.loader import load_config

async def test_browsing():
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    config = load_config()
    
    proxy = config.tools.web.proxy if config.tools.web else None
    tool = BrowserTool(proxy=proxy)
    
    print("🚀 Starting Deep Browsing Test (Public)...")
    
    # Use a public repo that is definitely indexable and responsive
    url = "https://github.com/GoogleCloudPlatform/generative-ai"
    print(f"🌐 Step 1: Browsing public repo main page: {url}")
    browse_result = await tool.execute(action="browse", url=url)
    print(f"✅ Browse Result Snippet: {browse_result[:1000]}...")
    
    if "repository" in browse_result.lower() or "google" in browse_result.lower():
        print("📁 Step 2: Key content verified in browse result.")
    else:
        print("❌ Step 2: Content verification failed.")
        
    print("🏁 Browsing Test Finished.")

if __name__ == "__main__":
    asyncio.run(test_browsing())
