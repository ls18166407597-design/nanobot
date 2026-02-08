import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from nanobot.agent.tools.gmail import GmailTool

async def test_gmail_deep_dive():
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    tool = GmailTool()
    
    print("🚀 Starting Phase 16 Test 1: Gmail Deep Dive...")
    
    # 1. Check status
    print("📧 Step 1: Checking mailbox status...")
    status_res = await tool.execute(action="status")
    print(f"✅ Status Result:\n{status_res}")
    
    # 2. List with limit
    print("\n📧 Step 2: Listing last 3 emails...")
    list_res = await tool.execute(action="list", limit=3)
    print(f"✅ List Result (ID Check):\n{list_res}")
    
    print("\n🏁 Gmail Deep Dive Finished.")

if __name__ == "__main__":
    asyncio.run(test_gmail_deep_dive())
