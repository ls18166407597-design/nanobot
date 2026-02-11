import sys
import os
import json
import argparse
from pathlib import Path

# Load contacts
CONTACTS_FILE = Path(__file__).parent / "contacts.json"
SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
APP_SCRIPT_DIR_MAP = {
    "telegram": SCRIPTS_ROOT / "telegram",
    "wechat": SCRIPTS_ROOT / "wechat",
}

def load_contacts():
    if not CONTACTS_FILE.exists():
        return {}
    with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_contacts(contacts):
    with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2, ensure_ascii=False)
    print(f"✅ Contacts saved to {CONTACTS_FILE}")

def list_contacts(contacts):
    print(f"📋 Contact List ({len(contacts)} entries):")
    print("-" * 40)
    for alias, info in contacts.items():
        print(f"• Alias: {alias}")
        print(f"  Name : {info['name']}")
        print(f"  App  : {info['app']}")
        if "description" in info:
            print(f"  Note : {info['description']}")
        print("-" * 40)

def add_contact(contacts, alias, name, app, description=None):
    alias = alias.lower().strip()
    if alias in contacts:
        print(f"⚠️ Warning: Overwriting existing contact '{alias}'")
    
    contacts[alias] = {
        "name": name,
        "app": app,
        "description": description or alias
    }
    save_contacts(contacts)
    print(f"✅ Added contact: {alias} -> {name} ({app})")

def remove_contact(contacts, alias):
    alias = alias.lower().strip()
    if alias not in contacts:
        print(f"❌ Error: Contact '{alias}' not found.")
        sys.exit(1)
    
    del contacts[alias]
    save_contacts(contacts)
    print(f"✅ Removed contact: {alias}")

def validate_contacts(contacts):
    print("🔍 Validating contacts.json...")
    errors = 0
    
    for alias, info in contacts.items():
        entry_errors = []
        if "name" not in info or not info["name"]:
            entry_errors.append("Missing 'name'")
        
        app = info.get("app")
        if not app:
            entry_errors.append("Invalid or missing 'app'")
        else:
            # Check if automation script exists
            app_lower = app.lower()
            potential_scripts = [
                f"automate_{app_lower}_keyboard_final.py",
                f"automate_{app_lower}_keyboard.py",
                f"automate_{app_lower}.py"
            ]
            app_dir = APP_SCRIPT_DIR_MAP.get(app_lower, SCRIPTS_ROOT)
            exists = any((app_dir / s).exists() for s in potential_scripts)
            if not exists:
                # Fallback global scan for non-standard app domains
                exists = any(list(SCRIPTS_ROOT.rglob(s)) for s in potential_scripts)
            if not exists:
                entry_errors.append(f"No automation script found for app '{app}'")
            
        if entry_errors:
            print(f"❌ Error in '{alias}': {', '.join(entry_errors)}")
            errors += 1
            
    if errors == 0:
        print("✅ Validation passed: All entries are structurally sound and scripts exist.")
    else:
        print(f"⚠️ Found {errors} entries with issues.")
    return errors == 0

def main():
    parser = argparse.ArgumentParser(description="Manage Desktop Messenger Contacts")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List
    subparsers.add_parser("list", help="List all contacts")
    
    # Validate
    subparsers.add_parser("validate", help="Validate contacts.json structure")

    # Add
    add_parser = subparsers.add_parser("add", help="Add or update a contact")
    add_parser.add_argument("alias", help="Short alias for the contact (e.g., 'mom', 'boss')")
    add_parser.add_argument("name", help="Real display name in the App")
    add_parser.add_argument("app", help="App to use (e.g., WeChat, Telegram, Slack)")
    add_parser.add_argument("--note", help="Optional description")

    # Remove
    rm_parser = subparsers.add_parser("remove", help="Remove a contact")
    rm_parser.add_argument("alias", help="Alias of the contact to remove")

    args = parser.parse_args()
    contacts = load_contacts()

    if args.command == "list":
        list_contacts(contacts)
    elif args.command == "validate":
        validate_contacts(contacts)
    elif args.command == "add":
        add_contact(contacts, args.alias, args.name, args.app, args.note)
    elif args.command == "remove":
        remove_contact(contacts, args.alias)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
