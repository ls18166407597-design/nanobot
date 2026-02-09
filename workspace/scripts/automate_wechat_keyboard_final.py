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

async def automate_wechat_keyboard_final(contact_name, message_content, keep_open=False):
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    # vision = MacVisionTool() # Not strictly needed if we trust the keyboard flow, but kept for imports
    
    print(f"🚀 Starting WeChat Automation (Target: {contact_name})...")
    
    # Secure Handling: If message is in clipboard, capture it NOW before search overwrites it
    if message_content == "[FROM_CLIPBOARD]":
        try:
            print("📋 Capturing message from clipboard...")
            message_content = subprocess.check_output(["pbpaste"], text=True)
            if not message_content:
                print("⚠️ Warning: Clipboard is empty.")
        except Exception as e:
            print(f"❌ Error reading clipboard: {e}")
            sys.exit(1)
    
    # helper to paste text safely
    def paste_text(text):
        # Explicitly set the clipboard every time to avoid race conditions
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
            
        # Use AppleScript only to trigger Cmd+V
        script = 'tell application "System Events" to key code 9 using command down'
        subprocess.run(["osascript", "-e", script], check=True)
        time.sleep(0.2)

    def press_enter():
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 36'])

    # 1. Activate WeChat (Auto-launch if closed)
    print("🔍 Activating WeChat (Will launch if not running)...")
    activate_script = 'tell application "WeChat" to activate'
    subprocess.run(["osascript", "-e", activate_script], check=True)
    
    # Wait for app to be ready
    time.sleep(2)
        
    time.sleep(1)
    
    # 2. Command + F to Focus Search
    print("🔍 Cmd+F to Focus Search...")
    cmd_f_script = '''
    tell application "System Events"
        tell process "WeChat"
            set frontmost to true
            keystroke "f" using {command down}
            delay 0.8
        end tell
    end tell
    '''
    subprocess.run(["osascript", "-e", cmd_f_script])
    
    # 3. Paste Search Term
    print(f"📋 Pasting Contact: '{contact_name}'...")
    paste_text(contact_name)
    
    # CRITICAL DELAY: Wait for search results to populate
    print("⏳ Waiting 1.5s for search results...")
    time.sleep(1.5)
    
    # 4. Press Enter to Select
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

    # 7. Optional: Quit/Hide app
    if not keep_open:
        print("🤫 Closing WeChat to keep desktop clean...")
        quit_script = 'tell application "WeChat" to quit'
        subprocess.run(["osascript", "-e", quit_script])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automate sending WeChat message.')
    parser.add_argument('--contact', required=True, help='Name of the contact to message')
    parser.add_argument('--message', required=True, help='Message content to send')
    parser.add_argument('--keep-open', action='store_true', help='Keep the app open after sending')
    args = parser.parse_args()
    
    asyncio.run(automate_wechat_keyboard_final(args.contact, args.message, keep_open=args.keep_open))
