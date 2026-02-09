import json
import subprocess
import sys
import os
import time

# 配置路径
WORKSPACE_DIR = "/Users/liusong/Downloads/nanobot/workspace"
CONTACTS_FILE = os.path.join(WORKSPACE_DIR, "scripts/contacts.json")
SMART_SEND_SCRIPT = os.path.join(WORKSPACE_DIR, "scripts/smart_send.py")

def main():
    # 1. 读取联系人
    try:
        with open(CONTACTS_FILE, 'r', encoding='utf-8') as f:
            contacts = json.load(f)
    except Exception as e:
        print(f"Error reading contacts.json: {e}")
        sys.exit(1)

    # 2. 筛选 Telegram 联系人
    telegram_contacts = []
    for alias, info in contacts.items():
        if info.get('app') == 'Telegram':
            telegram_contacts.append(alias)

    print(f"Found {len(telegram_contacts)} Telegram contacts: {', '.join(telegram_contacts)}")

    # 3. 批量发送
    message = "签到"
    success_count = 0
    fail_count = 0

    for alias in telegram_contacts:
        print(f"Sending to {alias}...")
        try:
            # 调用 smart_send.py
            cmd = [sys.executable, SMART_SEND_SCRIPT, alias, message]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Sent to {alias}")
                success_count += 1
            else:
                print(f"❌ Failed to send to {alias}: {result.stderr.strip()}")
                fail_count += 1
            
            # 稍微延时，避免操作过快
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error sending to {alias}: {e}")
            fail_count += 1

    print(f"\nBatch send complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    main()
