import asyncio
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from nanobot.agent.tools.mac import MacTool
from nanobot.agent.tools.mac_vision import MacVisionTool

async def test_adaptive_perception():
    # Force NANOBOT_HOME
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    
    mac = MacTool()
    vision = MacVisionTool(confirm_mode="warn")
    
    print("🚀 Starting Adaptive Environment Perception Test...")
    
    # 1. Identify Frontmost App
    print("🔍 Step 1: Identifying frontmost application...")
    front_app_res = await mac.execute(action="get_frontmost_app")
    print(f"✅ Result: {front_app_res}")
    
    if "Frontmost App:" not in front_app_res:
        print("❌ Failed to identify application.")
        return

    app_name = front_app_res.replace("Frontmost App: ", "").strip()
    
    # 2. Perform Targeted OCR
    print(f"📸 Step 2: Performing targeted OCR for application '{app_name}'...")
    vision_res = await vision.execute(action="look_at_screen", app_name=app_name, confirm=True)
    
    try:
        data = json.loads(vision_res)
        print(f"✅ Success. Identified {len(data)} text blocks in {app_name}'s window.")
        if len(data) > 0:
            print(f"Sample Text: '{data[0]['text']}'")
    except Exception as e:
        print(f"⚠️ OCR Result analysis failed (or no text found): {vision_res[:300]}...")

    print("🏁 Adaptive Perception Test Finished.")

if __name__ == "__main__":
    asyncio.run(test_adaptive_perception())
