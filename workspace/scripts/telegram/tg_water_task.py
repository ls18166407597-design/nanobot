import random
import subprocess
import time
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
SMART_SEND = SCRIPTS_ROOT / "dispatch" / "smart_send.py"

def run_command(cmd):
    print(f"🚀 Executing: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Execution error: {e}")
        return False

def main():
    msgs = ['签到']
    
    # 1. Ensure Telegram is open
    print("📂 Opening Telegram...")
    subprocess.run(['open', '-a', 'Telegram'])
    time.sleep(5)
    
    # 2. Account: 生如夏花
    msg1 = random.choice(msgs)
    print(f"\n👤 Account [生如夏花] -> Message: {msg1}")
    cmd1 = [
        sys.executable, str(SMART_SEND),
        "--all", "DUMMY_CONTACT", msg1, 
        "--account", "生如夏花", 
        "--app", "Telegram"
    ]
    success1 = run_command(cmd1)
    
    # 3. Account: 小李
    msg2 = random.choice(msgs)
    print(f"\n👤 Account [小李] -> Message: {msg2}")
    cmd2 = [
        sys.executable, str(SMART_SEND),
        "--all", "DUMMY_CONTACT", msg2, 
        "--account", "小李", 
        "--app", "Telegram", 
        "--close"
    ]
    success2 = run_command(cmd2)
    
    if success1 and success2:
        print("\n✨ All tasks completed successfully!")
    else:
        print("\n⚠️ Some tasks failed, but execution finished.")
        # We don't exit with 1 here to avoid "unexpected termination" if it's just a minor UI glitch
        # but the script actually finished.

if __name__ == "__main__":
    main()
