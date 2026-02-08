
import asyncio
import os
from nanobot.agent.tools.gmail import GmailTool

async def test_gmail():
    # Set NANOBOT_HOME to use the correct config
    if not os.getenv("NANOBOT_HOME"):
        os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    
    print("Initializing GmailTool...")
    tool = GmailTool()
    
    print("Executing action: list...")
    try:
        result = await tool.execute(action="list", limit=5)
        print("\n✅ Result:")
        print(result[:500] + "..." if len(result) > 500 else result)
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gmail())
