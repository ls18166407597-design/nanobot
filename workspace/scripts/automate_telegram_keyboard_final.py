import asyncio
import os
import sys
import json
import time
import subprocess
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

import argparse

async def automate_telegram_keyboard_final(contact_name, message_content):
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    # vision = MacVisionTool() # Not strictly needed if we trust the keyboard flow, but kept for imports
    
    print(f"🚀 Starting Telegram Automation (Target: {contact_name})...")
    
    # helper to paste text
    def paste_text(text):
        script = f'''
        set the clipboard to "{text}"
        tell application "System Events"
            key code 9 using command down -- Cmd+V
            delay 0.2
        end tell
        '''
        subprocess.run(["osascript", "-e", script])

    def press_enter():
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 36'])

    # 1. Activate Telegram
    print("🔍 Activating Telegram...")
    subprocess.run(["osascript", "-e", 'tell application "Telegram" to activate'])
    time.sleep(1)
    
    # 2. Command + K to Focus Search (Telegram Standard)
    print("🔍 Cmd+K to Focus Search...")
    cmd_k_script = '''
    tell application "System Events"
        tell process "Telegram"
            set frontmost to true
            keystroke "k" using {command down}
            delay 0.8  -- Give it time to pop up
        end tell
    end tell
    '''
    subprocess.run(["osascript", "-e", cmd_k_script])
    
    # 3. Paste Search Term
    print(f"📋 Pasting Contact: '{contact_name}'...")
    paste_text(contact_name)
    
    # CRITICAL DELAY: Wait for search results to populate
    print("⏳ Waiting 1.5s for search results...")
    time.sleep(1.5)
    
    # 4. Press Enter to Select (User Logic)
    print("↵ Pressing Enter to Select...")
    press_enter()
    
    # CRITICAL DELAY: Wait for chat window to open/focus
    print("⏳ Waiting 1.0s for chat focus...")
    time.sleep(1.0)
    
    # 5. Paste Message
    print("📋 Pasting Message...")
    paste_text(message_content)
    time.sleep(0.5)
    
    # 6. Press Enter to Send
    print("↵ Pressing Enter to Send...")
    press_enter()
    
    print("🏁 Automation complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automate sending Telegram message.')
    parser.add_argument('--contact', required=True, help='Name of the contact to message')
    parser.add_argument('--message', required=True, help='Message content to send')
    args = parser.parse_args()
    
    asyncio.run(automate_telegram_keyboard_final(args.contact, args.message))
