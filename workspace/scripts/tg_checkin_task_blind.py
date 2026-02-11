import json
import os
import sys
import time
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def file_lock(lock_file):
    lock_path = Path(lock_file)
    success = False
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w') as f:
            f.write(str(os.getpid()))
        success = True
    except FileExistsError:
        try:
            old_pid = int(lock_path.read_text().strip())
            os.kill(old_pid, 0)
            print(f"⚠️ Warning: Another task is already running (PID: {old_pid}). Skipping.")
            sys.exit(0)
        except (ProcessLookupError, ValueError, PermissionError):
            print("♻️ Stale lock file found. Taking over...")
            lock_path.unlink(missing_ok=True)
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w') as f:
                    f.write(str(os.getpid()))
                success = True
            except:
                sys.exit(1)
    try:
        yield
    finally:
        if success and lock_path.exists():
            try:
                if int(lock_path.read_text().strip()) == os.getpid():
                    lock_path.unlink()
            except:
                pass

def get_home_dir():
    current_path = Path(os.getcwd())
    for path in [current_path] + list(current_path.parents):
        if (path / ".home").exists():
            return path / ".home"
    return current_path / ".home"

# Load contacts
CONTACTS_FILE = Path("scripts/contacts.json")

def load_contacts():
    with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def run_send(contact_name, message, switch=False, close=False):
    cmd = [
        sys.executable, "scripts/automate_telegram_blind.py",
        "--contact", contact_name,
        "--message", message
    ]
    if switch:
        cmd.extend(["--account", "SWITCH"])
    if close:
        cmd.append("--close")
    
    print(f"🚀 Executing: {' '.join(cmd)}")
    subprocess.run(cmd)

def main():
    contacts = load_contacts()
    # Filter for Telegram contacts
    # Filter for Telegram contacts and deduplicate
    tg_contacts = sorted(list(set(info["name"] for info in contacts.values() if info["app"].lower() == "telegram")))
    
    if not tg_contacts:
        print("❌ No Telegram contacts found.")
        return

    print(f"📂 Opening Telegram...")
    subprocess.run(['open', '-a', 'Telegram'])
    time.sleep(5)

    lock_file = get_home_dir() / "tg_automation.lock"
    with file_lock(lock_file):
        # --- Account 1 (Current) ---
        print("\n👤 Sending from Account 1...")
        for i, name in enumerate(tg_contacts):
            run_send(name, "签到")
            time.sleep(1)

        # --- Account 2 (Switch) ---
        print("\n👤 Switching to Account 2...")
        for i, name in enumerate(tg_contacts):
            is_first = (i == 0)
            is_last = (i == len(tg_contacts) - 1)
            run_send(name, "签到", switch=is_first, close=is_last)
            time.sleep(2)

    print("\n✨ All tasks completed in Blind Mode!")

if __name__ == "__main__":
    main()
