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

async def automate_telegram_keyboard_final(contact_name=None, message_content=None, keep_open=True, target_account=None, info_only=False):
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    # vision = MacVisionTool() # Not strictly needed if we trust the keyboard flow, but kept for imports
    
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
        # Explicitly set the clipboard every time to avoid race conditions
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
            
        # Use AppleScript only to trigger Cmd+V
        script = 'tell application "System Events" to key code 9 using command down'
        subprocess.run(["osascript", "-e", script], check=True)
        time.sleep(0.2)

    def press_enter():
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 36'])

    def get_current_account(retries=5):
        for i in range(retries):
            try:
                cmd = 'tell application "System Events" to get title of window 1 of process "Telegram"'
                title = subprocess.check_output(["osascript", "-e", cmd], text=True).strip()
                
                # Format A: "MyContact @ MyAccount"
                if " @ " in title:
                    acc = title.split(" @ ")[-1]
                    if acc and acc != "Unknown":
                        return acc
                
                # Format B: just "Telegram (MyAccount)"
                if "(" in title and ")" in title:
                    acc = title.split("(")[-1].split(")")[0]
                    if acc:
                        return acc
                
                # Format C: If it's just a username or something, we might need vision fallback
                # but for most people, the name is in the title.
                if title and title != "Telegram":
                    # Heuristic: if title is short and looks like a name
                    return title
                    
                print(f"⏳ Waiting for window title to update (try {i+1}/{retries})...")
            except Exception as e:
                print(f"⚠️ Warning: Failed to read title: {e}")
            time.sleep(1.0)
        return "Unknown"

    def switch_account(target):
        print(f"🔄 Toggling Telegram account to reach '{target}'...")
        pre_switch_acc = get_current_account(retries=1)
        
        # Cmd + Shift + M to open account menu
        subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "m" using {command down, shift down}'])
        time.sleep(1.5)
        # Press Down arrow once
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 125'])
        time.sleep(0.5)
        press_enter()
        
        # VERIFICATION
        print("⏳ Verification: Waiting for account switch to register...")
        for _ in range(10):
            time.sleep(1.0)
            current_acc = get_current_account(retries=1)
            if current_acc != pre_switch_acc and current_acc != "Unknown":
                print(f"✅ Successfully switched to account: {current_acc}")
                return
            
        print("⚠️ Warning: Account switch may have failed or title didn't update.")

    # 1. Activate Telegram (Auto-launch if closed)
    print("🔍 Activating Telegram (Will launch if not running)...")
    activate_script = 'tell application "Telegram" to activate'
    subprocess.run(["osascript", "-e", activate_script], check=True)
    
    # Wait for app to be ready
    time.sleep(2)

    # 1b. Handle info_only request
    if info_only:
        acc = get_current_account()
        print(f"👤 Current Telegram Account: {acc}")
        return

    # 2. Smart Introspective Account Check & Switch
    if target_account:
        current_acc = get_current_account()
        print(f"👤 Current account: {current_acc} | Target: {target_account}")
        
        # Exact match or substring match (case-insensitive)
        is_already_target = isinstance(target_account, str) and target_account.lower() in current_acc.lower()
        
        if is_already_target:
            print(f"✨ Already on target account '{current_acc}'. No switch needed.")
        else:
            # Need to switch
            switch_account(target_account)
            
            # Post-switch verification
            final_acc = get_current_account(retries=2)
            if target_account.lower() not in final_acc.lower():
                print(f"❌ Error: Failed to switch to target account '{target_account}'. Still on '{final_acc}'.")
                print("⚠️ Aborting delivery to prevent sending from wrong account.")
                sys.exit(1)
            print(f"✅ Verified: Successfully reached target account '{final_acc}'.")
        
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

    # 7. Optional: Quit/Hide app
    if not keep_open:
        print("🤫 Closing Telegram to keep desktop clean...")
        quit_script = 'tell application "Telegram" to quit'
        subprocess.run(["osascript", "-e", quit_script])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automate sending Telegram message.')
    parser.add_argument('--contact', help='Name of the contact to message')
    parser.add_argument('--message', help='Message content to send')
    parser.add_argument('--keep-open', action='store_true', default=True, help='Keep the app open after sending (default: True)')
    parser.add_argument('--close', action='store_true', help='Force close the app after sending')
    parser.add_argument('--account', help='Telegram account name (e.g. "小李") or index (1 or 2)')
    parser.add_argument('--info', action='store_true', help='Only print current account info and exit')
    args = parser.parse_args()
    
    if not args.info and (not args.contact or not args.message):
        parser.error("--contact and --message are required unless --info is used")

    # Handle keep_open logic
    final_keep_open = not args.close

    asyncio.run(automate_telegram_keyboard_final(
        contact_name=args.contact, 
        message_content=args.message, 
        keep_open=final_keep_open, 
        target_account=args.account,
        info_only=args.info
    ))
