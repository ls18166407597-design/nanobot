import email
import imaplib
import json
import os
import smtplib
from email.header import decode_header
from email.message import EmailMessage
from typing import Any

from nanobot.agent.tools.base import Tool

from nanobot.config.loader import get_data_dir


class GmailTool(Tool):
    """Tool for interacting with Gmail via IMAP/SMTP (App Password)."""

    name = "gmail"
    description = """
    Interact with Gmail using standard protocols (IMAP/SMTP).
    Capabilities:
    - List recent emails
    - Read emails
    - Send emails
    - Check mailbox status (total count, unread count)

    Setup:
    Requires 'gmail_config.json' in your nanobot home with:
    {
        "email": "your_email@gmail.com",
        "password": "your_app_password"
    }
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "read", "send", "setup", "status"],
                "description": "The action to perform.",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of emails to list (default 10).",
            },
            "email_id": {"type": "string", "description": "The ID of the email to read."},
            "to": {"type": "string", "description": "Recipient email address (for 'send')."},
            "subject": {"type": "string", "description": "Email subject (for 'send')."},
            "body": {"type": "string", "description": "Email body content (for 'send')."},
            "setup_email": {"type": "string", "description": "Email for setup."},
            "setup_password": {
                "type": "string",
                "description": "App password for setup.",
            },
        },
        "required": ["action"],
    }

    def _load_config(self):
        config_path = get_data_dir() / "gmail_config.json"
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_config(self, email, password):
        config_path = get_data_dir() / "gmail_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump({"email": email, "password": password}, f)

    async def execute(self, action: str, **kwargs: Any) -> str:
        if action == "setup":
            email_addr = kwargs.get("setup_email")
            password = kwargs.get("setup_password")
            if not email_addr or not password:
                return "Error: 'setup_email' and 'setup_password' are required for setup."
            self._save_config(email_addr, password)
            return "Gmail configuration saved successfully."

        config = self._load_config()
        if not config:
            return "Error: Gmail not configured. Please action='setup' with setup_email and setup_password (use an App Password)."

        try:
            if action == "list":
                return self._list_emails(config, kwargs.get("limit", 10))
            elif action == "read":
                email_id = kwargs.get("email_id")
                if not email_id:
                    return "Error: 'email_id' is required for 'read' action."
                return self._read_email(config, email_id)
            elif action == "send":
                return self._send_email(config, kwargs)
            elif action == "status":
                return self._status(config)
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Gmail Tool Error: {str(e)}"

    def _list_emails(self, config, limit):
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(config["email"], config["password"])
        mail.select("inbox")

        _, search_data = mail.search(None, "ALL")
        mail_ids = search_data[0].split()

        # Get last N emails
        recent_ids = mail_ids[-limit:]

        output = []
        for i in reversed(recent_ids):
            _, msg_data = mail.fetch(i, "(RFC822)")
            if not msg_data or msg_data[0] is None:
                continue
            raw_email = msg_data[0][1]
            if not isinstance(raw_email, bytes):
                continue
            msg = email.message_from_bytes(raw_email)

            subject = self._decode_header(msg["Subject"])
            from_addr = self._decode_header(msg["From"])

            email_id_str = i.decode() if isinstance(i, bytes) else str(i)
            output.append(f"ID: {email_id_str} | From: {from_addr} | Subject: {subject}")

        mail.logout()
        if not output:
            return "No emails found."
        return "\n".join(output)

    def _read_email(self, config, email_id):
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(config["email"], config["password"])
        mail.select("inbox")

        _, msg_data = mail.fetch(email_id, "(RFC822)")
        if not msg_data or msg_data[0] is None:
            return "Email not found."

        raw_email = msg_data[0][1]
        if not isinstance(raw_email, bytes):
            return "Error: Fetched message is not in expected format."
            
        msg = email.message_from_bytes(raw_email)

        subject = self._decode_header(msg["Subject"])
        from_addr = self._decode_header(msg["From"])
        date = self._decode_header(msg["Date"])

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body += payload.decode(errors="ignore")
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode(errors="ignore")

        mail.logout()
        return f"From: {from_addr}\nDate: {date}\nSubject: {subject}\n\nBody:\n{body[:2000]}..."

    def _send_email(self, config, kwargs):
        to = kwargs.get("to")
        subject = kwargs.get("subject")
        body = kwargs.get("body")

        if not to or not subject or not body:
            return "Error: 'to', 'subject', and 'body' are required for sending."

        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = config["email"]
        msg["To"] = to

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(config["email"], config["password"])
            smtp.send_message(msg)

        return "Email sent successfully."

    def _decode_header(self, header):
        if not header:
            return ""
        decoded_list = decode_header(header)
        text = ""
        for decoded_bytes, charset in decoded_list:
            if isinstance(decoded_bytes, bytes):
                if charset:
                    try:
                        text += decoded_bytes.decode(charset)
                    except Exception:
                        text += decoded_bytes.decode("utf-8", errors="ignore")
                else:
                    text += decoded_bytes.decode("utf-8", errors="ignore")
            else:
                text += str(decoded_bytes)
        return text

    def _status(self, config):
        """Get mailbox status (total and unread count)."""
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(config["email"], config["password"])
        
        # STATUS command allows checking folder status without selecting it
        # Request MESSAGES (total) and UNSEEN (unread) counts
        typ, data = mail.status("INBOX", "(MESSAGES UNSEEN)")
        mail.logout()

        if typ != "OK":
            return "Error: Failed to retrieve mailbox status."

        # Response format: b'"INBOX" (MESSAGES 123 UNSEEN 5)'
        status_str = data[0].decode()
        
        # Simple parsing
        import re
        total_match = re.search(r"MESSAGES\s+(\d+)", status_str)
        unread_match = re.search(r"UNSEEN\s+(\d+)", status_str)
        
        total = total_match.group(1) if total_match else "?"
        unread = unread_match.group(1) if unread_match else "?"
        
        return f"📧 Inbox Status:\n- Total Emails: {total}\n- Unread Emails: {unread}"
