import subprocess
import time
import sys
import os
import json
from pathlib import Path

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
    tg_contacts = [info["name"] for info in contacts.values() if info["app"].lower() == "telegram"]
    
    if not tg_contacts:
        print("❌ No Telegram contacts found.")
        return

    print(f"📂 Opening Telegram...")
    subprocess.run(['open', '-a', 'Telegram'])
    time.sleep(5)

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
