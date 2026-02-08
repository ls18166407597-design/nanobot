import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from nanobot.agent.tools.github import GitHubTool
from nanobot.agent.tools.memory import MemoryTool
from nanobot.agent.tools.gmail import GmailTool

async def test_robustness():
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    workspace = Path(".").resolve()
    
    github = GitHubTool()
    memory = MemoryTool(workspace=workspace)
    gmail = GmailTool()
    
    print("🚀 Starting Phase 16 Test 3: Robustness & Edge Cases...")
    
    # 1. GitHub Empty Multi-parameters
    print("📦 Step 1: Testing GitHub with empty repo string...")
    gh_res = await github.execute(action="list_commits", repo="", count=3)
    print(f"✅ GitHub Error Handling: {gh_res}")
    
    # 2. Gmail Invalid ID
    print("\n📧 Step 2: Testing Gmail with invalid ID...")
    gmail_res = await gmail.execute(action="read", email_id="999999")
    print(f"✅ Gmail Error Handling: {gmail_res}")
    
    # 3. Memory Search no results
    print("\n🧠 Step 3: Testing Memory search with nonsense query...")
    mem_res = await memory.execute(action="search", query="XYZZY_BLAH_BLAH_UNKNOWN")
    print(f"✅ Memory Error Handling: {mem_res}")
    
    print("\n🏁 Robustness Test Finished.")

if __name__ == "__main__":
    asyncio.run(test_robustness())
