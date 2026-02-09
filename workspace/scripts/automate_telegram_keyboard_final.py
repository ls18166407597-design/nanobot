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
    
    # helper to paste text safely
    def paste_text(text):
        # Use pbcopy to set the clipboard safely (avoids injections and quote/newline issues)
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
        # Use AppleScript only to trigger Cmd+V
        script = 'tell application "System Events" to key code 9 using command down'
        subprocess.run(["osascript", "-e", script], check=True)
        time.sleep(0.2)

    def press_enter():
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 36'])

    # 1. Activate Telegram & Health Check
    print("🔍 Checking if Telegram is running and activating...")
    check_script = '''
    tell application "System Events"
        set isRunning to exists (process "Telegram")
        if isRunning then
            tell application "Telegram" to activate
            return "OK"
        else
            return "NOT_RUNNING"
        end if
    end tell
    '''
    process_check = subprocess.run(["osascript", "-e", check_script], capture_output=True, text=True)
    if "NOT_RUNNING" in process_check.stdout:
        print("❌ Error: Telegram is not running. Please start the app first.")
        sys.exit(1)
        
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
