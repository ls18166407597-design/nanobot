import asyncio
import os
import sys
import json
import time
import subprocess
from pathlib import Path
import argparse
import signal
from contextlib import contextmanager

# Add project root to sys.path
sys.path.append(os.getcwd())

@contextmanager
def file_lock(lock_file):
    lock_path = Path(lock_file)
    success = False
    
    # Try once or take over stale
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w') as f:
            f.write(str(os.getpid()))
        success = True
    except FileExistsError:
        try:
            old_pid = int(lock_path.read_text().strip())
            os.kill(old_pid, 0)
            print(f"⚠️ Warning: Another automation is already running (PID: {old_pid}). Skipping.")
            sys.exit(0)
        except (ProcessLookupError, ValueError, PermissionError):
            print("♻️ Stale lock file found. Taking over...")
            lock_path.unlink(missing_ok=True)
            # Second attempt after clearing stale
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w') as f:
                    f.write(str(os.getpid()))
                success = True
            except:
                print("❌ Failed to acquire lock after clearing stale.")
                sys.exit(1)

    try:
        yield
    finally:
        if success and lock_path.exists():
            try:
                current_lock_pid = int(lock_path.read_text().strip())
                if current_lock_pid == os.getpid():
                    lock_path.unlink()
            except:
                pass

async def automate_telegram_keyboard_blind(
    contact_name=None,
    message_content=None,
    keep_open=True,
    target_account=None,
    info_only=False,
    skip_lock=False,
):
    # Find project root (looking for .home)
    current_path = Path(os.getcwd())
    home_dir = None
    for path in [current_path] + list(current_path.parents):
        if (path / ".home").exists():
            home_dir = path / ".home"
            break
            
    if not home_dir:
        # Fallback to current working directory
        home_dir = current_path / ".home"
        home_dir.mkdir(exist_ok=True)
        
    os.environ["NANOBOT_HOME"] = str(home_dir.absolute())
    lock_file = home_dir / "tg_automation.lock"
    if skip_lock:
        print(f"🔓 Skip lock enabled. Parent task holds lock: {lock_file.absolute()}")
    else:
        print(f"🔒 Using Lock File: {lock_file.absolute()}")

    def run_flow() -> None:
        nonlocal message_content
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

    if skip_lock:
        run_flow()
    else:
        with file_lock(lock_file):
            run_flow()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Automate sending Telegram message (Blind Mode).')
    parser.add_argument('--contact', help='Name of the contact to message')
    parser.add_argument('--message', help='Message content to send')
    parser.add_argument('--close', action='store_true', help='Force close the app after sending')
    parser.add_argument('--account', help='Set to "SWITCH" to perform a blind account switch before sending')
    parser.add_argument('--skip-lock', action='store_true', help='Skip lock (use when parent task already holds lock)')
    args = parser.parse_args()
    
    asyncio.run(automate_telegram_keyboard_blind(
        contact_name=args.contact, 
        message_content=args.message, 
        keep_open=not args.close, 
        target_account=args.account,
        skip_lock=args.skip_lock,
    ))
