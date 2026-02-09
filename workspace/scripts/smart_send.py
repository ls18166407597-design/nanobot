import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

# Load contacts
CONTACTS_FILE = Path(__file__).parent / "contacts.json"

def load_contacts():
    if not CONTACTS_FILE.exists():
        print(f"❌ Error: Contacts file not found at {CONTACTS_FILE}")
        return {}
    with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def find_contact(query, contacts):
    query = query.lower().strip()
    
    # 1. Exact match on alias (Highest priority)
    if query in contacts:
        return contacts[query]
    
    # 2. Collect all potential matches
    matches = []
    for alias, info in contacts.items():
        name = info["name"].lower()
        if alias.startswith(query) or name.startswith(query):
            matches.append((alias, info, "prefix"))
        elif query in alias or query in name:
            matches.append((alias, info, "contains"))
            
    if not matches:
        return None
        
    # 3. Sort matches: prefix first, then shortest length (least ambiguous)
    # Sorting key: (type_weight, length_of_alias)
    type_weights = {"prefix": 0, "contains": 1}
    matches.sort(key=lambda x: (type_weights[x[2]], len(x[0])))
    
    # If the first match is significantly better or unique, return it
    return matches[0][1]

def main():
    parser = argparse.ArgumentParser(description="Smart Desktop Messenger Dispatcher")
    parser.add_argument("contact", help="Name or alias of the recipient")
    parser.add_argument("message", help="Message content to send")
    args = parser.parse_args()

    contacts = load_contacts()
    target = find_contact(args.contact, contacts)

    if not target:
        print(f"❌ Unknown contact: '{args.contact}'")
        print("Available contacts:")
        for k, v in contacts.items():
            print(f"  - {k} ({v['name']} on {v['app']})")
        sys.exit(1)

    print(f"✅ Found contact: {target['name']} on {target['app']}")
    
    # Dispatch
    result = None
    env = os.environ.copy()
    env["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    
    script_path = None
    if target["app"] == "WeChat":
        script_path = Path(__file__).parent / "automate_wechat_keyboard_final.py"
    elif target["app"] == "Telegram":
        script_path = Path(__file__).parent / "automate_telegram_keyboard_final.py"
    else:
        print(f"❌ Unsupported app: {target['app']}")
        sys.exit(1)

    cmd = [sys.executable, str(script_path), "--contact", target["name"], "--message", args.message]
    
    masked_cmd = cmd[:-1] + ["[HIDDEN]"]
    print(f"🚀 Dispatching to {target['app']} script...")
    print(f"Command: {' '.join(masked_cmd)}")
    
    try:
        subprocess.run(cmd, env=env, check=True)
        print(f"✅ Message sent successfully to {target['name']}!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error sending message: {e}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
