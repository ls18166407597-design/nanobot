import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from nanobot.agent.tools.github import GitHubTool

async def test_ecosystem_fixed():
    tool = GitHubTool()
    
    print("🚀 Starting Ecosystem Interaction Test (GitHub Fixed)...")
    
    # 1. List Commits
    repo_full = "ls18166407597-design/nanobot"
    print(f"📦 Step 1: Listing recent commits for '{repo_full}'...")
    result = await tool.execute(action="list_commits", repo=repo_full, count=5)
    
    if "Error" not in result:
        print(f"✅ Success. Retrieved commits. Result Snippet: {result[:500]}...")
    else:
        print(f"❌ GitHub Error: {result}")

    print("🏁 Ecosystem Test Finished.")

if __name__ == "__main__":
    asyncio.run(test_ecosystem_fixed())
