import asyncio
import os
import sys
import json
import time
import subprocess
from pathlib import Path
import argparse

# Add project root to sys.path
sys.path.append(os.getcwd())

async def automate_telegram_keyboard_blind(contact_name=None, message_content=None, keep_open=True, target_account=None, info_only=False):
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    
    print(f"🚀 Starting Telegram Automation (Target: {contact_name})...")
    
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
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
        script = 'tell application "System Events" to key code 9 using command down'
        subprocess.run(["osascript", "-e", script], check=True)
        time.sleep(0.2)

    def press_enter():
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 36'])

    def blind_switch():
        print("🔄 Performing Blind Account Switch (Cmd+Shift+M -> Down -> Enter)...")
        # Cmd + Shift + M to open account menu
        subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "m" using {command down, shift down}'])
        time.sleep(1.5)
        # Press Down arrow once
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 125'])
        time.sleep(0.5)
        press_enter()
        # Wait for UI to settle
        time.sleep(3.0)
        print("✅ Blind switch command sent.")

    # 1. Activate Telegram
    print("🔍 Activating Telegram...")
    activate_script = 'tell application "Telegram" to activate'
    subprocess.run(["osascript", "-e", activate_script], check=True)
    time.sleep(2)

    # 2. Account Logic: Blind Switch if requested
    # Note: In blind mode, we don't check current account, we just switch if it's the second account's turn.
    # The caller (tg_water_task.py) should manage the sequence.
    if target_account == "SWITCH":
        blind_switch()
        
    time.sleep(1)
    
    # 3. Command + K to Focus Search
    print("🔍 Cmd+K to Focus Search...")
    cmd_k_script = '''
    tell application "System Events"
        tell process "Telegram"
            set frontmost to true
            keystroke "k" using {command down}
            delay 0.8
        end tell
    end tell
    '''
    subprocess.run(["osascript", "-e", cmd_k_script])
    
    # 4. Paste Search Term
    print(f"📋 Pasting Contact: '{contact_name}'...")
    paste_text(contact_name)
    time.sleep(1.5)
    
    # 5. Press Enter to Select
    print("↵ Pressing Enter to Select...")
    press_enter()
    time.sleep(1.0)
    
    # 6. Paste Message
    print("📋 Pasting Message...")
    paste_text(message_content)
    time.sleep(0.5)
    
    # 7. Press Enter to Send
    print("↵ Pressing Enter to Send...")
    press_enter()
    
    print("🏁 Automation complete.")

    # 8. Optional: Quit
    if not keep_open:
        print("🤫 Closing Telegram...")
        quit_script = 'tell application "Telegram" to quit'
        subprocess.run(["osascript", "-e", quit_script])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automate sending Telegram message (Blind Mode).')
    parser.add_argument('--contact', help='Name of the contact to message')
    parser.add_argument('--message', help='Message content to send')
    parser.add_argument('--close', action='store_true', help='Force close the app after sending')
    parser.add_argument('--account', help='Set to "SWITCH" to perform a blind account switch before sending')
    args = parser.parse_args()
    
    asyncio.run(automate_telegram_keyboard_blind(
        contact_name=args.contact, 
        message_content=args.message, 
        keep_open=not args.close, 
        target_account=args.account
    ))
