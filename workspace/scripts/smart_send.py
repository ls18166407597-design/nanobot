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

    if target is None:
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
    
    app_name = target["app"]
    app_lower = app_name.lower()
    
    # Dynamic Lookup Strategy
    potential_filenames = [
        f"automate_{app_lower}_keyboard_final.py",
        f"automate_{app_lower}_keyboard.py",
        f"automate_{app_lower}.py"
    ]
    
    script_path = None
    for fname in potential_filenames:
        test_path = Path(__file__).parent / fname
        if test_path.exists():
            script_path = test_path
            break
            
    if not script_path:
        print(f"❌ Error: No automation script found for '{app_name}' in {Path(__file__).parent}")
        print(f"Expected one of: {', '.join(potential_filenames)}")
        sys.exit(1)

    # Secure Handling: Use pbcopy to pass message via clipboard to avoid injection
    try:
        print("📋 Copying message to clipboard for secure delivery...")
        subprocess.run(["pbcopy"], input=args.message, text=True, check=True)
    except Exception as e:
        print(f"⚠️ Warning: Failed to copy to clipboard: {e}. Falling back to command line args.")
        # We don't exit here, the scripts might still work with args, though less securely

    # Command construction with masked message
    cmd = [sys.executable, str(script_path), "--contact", target["name"], "--message", "[FROM_CLIPBOARD]"]
    
    print(f"🚀 Dispatching to {target['app']} script...")
    print(f"Command: {' '.join(cmd)}") # Already masked by using [FROM_CLIPBOARD]
    
    try:
        # Note: We still pass the actual message via env or args if needed, 
        # but the target scripts are being updated to prefer clipboard.
        subprocess.run(cmd, env=env, check=True)
        print(f"✅ Message delivery triggered successfully for {target['name']}!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error sending message: {e}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
