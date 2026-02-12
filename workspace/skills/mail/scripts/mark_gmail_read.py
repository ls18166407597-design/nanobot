import imaplib
import json
import os
from pathlib import Path

def mark_all_as_read():
    home_dir = Path(os.getenv("NANOBOT_HOME", Path.cwd() / ".home")).expanduser()
    config_path = home_dir / "tool_configs" / "gmail_config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    email_user = config['email']
    email_pass = config['password']
    
    # Connect to Gmail IMAP
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(email_user, email_pass)
    mail.select("inbox")
    
    # Search for all unread emails
    status, response = mail.search(None, 'UNSEEN')
    if status == 'OK':
        unread_ids = response[0].split()
        total_unread = len(unread_ids)
        print(f"Found {total_unread} unread emails.")
        
        # Mark as read in batches to avoid timeout
        batch_size = 100
        for i in range(0, total_unread, batch_size):
            batch = unread_ids[i:i+batch_size]
            batch_str = ",".join([id.decode() for id in batch])
            mail.store(batch_str, '+FLAGS', '\\Seen')
            print(f"Marked {i + len(batch)}/{total_unread} as read...")
            
    mail.logout()

if __name__ == "__main__":
    mark_all_as_read()
