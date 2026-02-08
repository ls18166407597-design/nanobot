import asyncio
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from nanobot.agent.tools.mac_vision import MacVisionTool

async def test_vision():
    tool = MacVisionTool(confirm_mode="warn")
    
    print("🚀 Starting macOS Perception Test...")
    
    # 1. Full Screen OCR
    print("📸 Step 1: Performing full screen OCR (look_at_screen)...")
    result = await tool.execute(action="look_at_screen", confirm=True)
    
    try:
        data = json.loads(result)
        print(f"✅ Full Screen OCR Success. Found {len(data)} text blocks.")
        if len(data) > 0:
            print(f"Sample: '{data[0]['text']}' at {data[0]['bbox']}")
    except Exception as e:
        print(f"❌ Full Screen OCR Error or No Text: {result[:200]}...")

    # 2. Targeted App Capture
    print("🖼️ Step 2: Capturing specific app window (e.g. Google Chrome)...")
    # We try Chrome since we know it might be open or Finder
    path = await tool.execute(action="capture_screen", app_name="Google Chrome", confirm=True)
    if os.path.exists(path):
        print(f"✅ Targeted Capture Success. Screenshot saved at: {path}")
    else:
        # Try Finder as fallback
        print("⚠️ Chrome not found, trying Finder...")
        path = await tool.execute(action="capture_screen", app_name="Finder", confirm=True)
        if os.path.exists(path):
            print(f"✅ Targeted Capture Success (Finder). Screenshot saved at: {path}")
        else:
            print(f"❌ Targeted Capture Failed: {path}")

    print("🏁 macOS Perception Test Finished.")

if __name__ == "__main__":
    asyncio.run(test_vision())
