import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from nanobot.agent.tools.memory import MemoryTool
from nanobot.agent.tools.knowledge import KnowledgeTool

async def test_rag():
    # Force NANOBOT_HOME to the local .home
    home_dir = Path(".").resolve() / ".home"
    os.environ["NANOBOT_HOME"] = str(home_dir)
    
    workspace = Path(".").resolve()
    memory = MemoryTool(workspace=workspace)
    knowledge = KnowledgeTool()
    
    print(f"🚀 Starting Memory & RAG Synergy Test (Home: {home_dir})...")
    
    # 1. Knowledge Search
    print("📚 Step 1: Searching knowledge...")
    # List a few files first to be sure
    k_dir = Path("nanobot/knowledge")
    if k_dir.exists():
        files = list(k_dir.glob("*.md"))
        print(f"   (Files in knowledge: {[f.name for f in files]})")
        
    knowledge_result = await knowledge.execute(action="search", query="Project")
    print(f"✅ Knowledge Result Snippet: {knowledge_result[:300]}...")
    
    # 2. Memory Storage
    print("🧠 Step 2: Storing a new tech insight in memory...")
    insight = "Phase 14 Test Insight: Memory search requires exact substring match for now."
    await memory.execute(action="append_daily", content=insight)
    print("✅ Memory added via append_daily.")
    
    # 3. Memory Search (Recall)
    print("🔍 Step 3: Recalling the insight from memory...")
    # Search for a word we definitely added
    recall_result = await memory.execute(action="search", query="substring match")
    print(f"✅ Recall Result: {recall_result}")

    print("🏁 Memory & RAG Test Finished.")

if __name__ == "__main__":
    asyncio.run(test_rag())
