import sys
import subprocess
import time

def send_telegram(name, message):
    script = f'''
    tell application "Telegram" to activate
    delay 0.5
    tell application "System Events"
        tell process "Telegram"
            -- 搜索联系人
            keystroke "k" using command down
            delay 0.2
            keystroke "{name}"
            delay 1.0
            keystroke return
            delay 0.5
            -- 发送消息
            keystroke "{message}"
            delay 0.5
            keystroke return
        end tell
    end tell
    '''
    subprocess.run(['osascript', '-e', script])

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: smart_send.py <name> <message>")
        sys.exit(1)
    
    name = sys.argv[1]
    message = sys.argv[2]
    send_telegram(name, message)
