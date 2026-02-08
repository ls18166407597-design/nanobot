import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from nanobot.agent.tools.github import GitHubTool
from nanobot.agent.tools.memory import MemoryTool
from nanobot.agent.tools.gmail import GmailTool

async def test_cross_tool_synergy():
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    workspace = Path(".").resolve()
    
    github = GitHubTool()
    memory = MemoryTool(workspace=workspace)
    gmail = GmailTool()
    
    print("🚀 Starting Phase 16 Test 2: Cross-Tool Synergy Loop...")
    
    # 1. GitHub Commits
    repo_full = "ls18166407597-design/nanobot"
    print(f"📦 Step 1: Listing last 3 commits for '{repo_full}'...")
    gh_res = await github.execute(action="list_commits", repo=repo_full, count=3)
    print(f"✅ GitHub Result Snippet: {gh_res[:200]}...")
    
    # 2. Store in Memory
    print("\n🧠 Step 2: Storing Dev Insight in Memory...")
    insight_content = f"Sync Test Insight - Repo: {repo_full}\nLatest Commits:\n{gh_res}"
    mem_res = await memory.execute(action="append_daily", content=insight_content)
    print(f"✅ Memory Result: {mem_res}")
    
    # 3. Draft/Send Gmail Report
    print("\n📧 Step 3: Drafting Gmail report...")
    report_body = f"Automated Nanobot Sync Report\n\nI have successfully synced the latest GitHub commits and stored them in your persistent memory.\n\nGitHub Data:\n{gh_res[:500]}..."
    
    # We use 'status' as a final check to ensure tool readiness for the final report
    gmail_status = await gmail.execute(action="status")
    print(f"✅ Gmail Status for final verification:\n{gmail_status}")
    
    print("\n🏁 Cross-Tool Synergy Test Finished.")

if __name__ == "__main__":
    asyncio.run(test_cross_tool_synergy())
