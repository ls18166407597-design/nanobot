import imaplib
import json
import os
from pathlib import Path

def mark_all_as_read():
    home_dir = Path(os.getenv("NANOBOT_HOME", Path.cwd() / ".home")).expanduser()
    config_path = home_dir / "tool_configs" / "qq_mail_config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    email_user = config['email']
    email_pass = config['password']
    
    # Connect to QQ Mail IMAP server
    mail = imaplib.IMAP4_SSL("imap.qq.com")
    mail.login(email_user, email_pass)
    
    # Select inbox
    mail.select("INBOX")
    
    # Search for all unread emails
    status, response = mail.search(None, 'UNSEEN')
    
    if status == 'OK':
        unread_ids = response[0].split()
        if not unread_ids:
            print("没有未读邮件。")
            return
        
        print(f"正在将 {len(unread_ids)} 封邮件标记为已读...")
        
        # Mark each unread email as read
        for e_id in unread_ids:
            mail.store(e_id, '+FLAGS', '\\Seen')
            
        print("所有邮件已成功标记为已读。")
    else:
        print("无法搜索未读邮件。")
    
    mail.logout()

if __name__ == "__main__":
    mark_all_as_read()
