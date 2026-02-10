import email
import imaplib
import json
import os
import smtplib
from email.header import decode_header
from email.message import EmailMessage
from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.config.loader import get_data_dir


class QQMailTool(Tool):
    """Tool for interacting with QQ Mail via IMAP/SMTP (Authorization Code)."""

    name = "qq_mail"
    description = """
    Interact with QQ Mail using standard protocols (IMAP/SMTP).
    Capabilities:
    - List recent emails
    - Read emails
    - Send emails
    - Check mailbox status (total count, unread count)

    Setup:
    Requires 'qq_mail_config.json' in your nanobot home with:
    {
        "email": "your_email@qq.com",
        "password": "your_authorization_code"
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
                "description": "Authorization code for setup.",
            },
        },
        "required": ["action"],
    }

    def _load_config(self):
        config_path = get_data_dir() / "qq_mail_config.json"
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_config(self, email, password):
        config_path = get_data_dir() / "qq_mail_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump({"email": email, "password": password}, f)

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        if action == "setup":
            email_addr = kwargs.get("setup_email")
            password = kwargs.get("setup_password")
            if not email_addr or not password:
                return ToolResult(
                    success=False, 
                    output="Error: 'setup_email' and 'setup_password' are required for setup.",
                    remedy="请提供 setup_email 和 setup_password 参数。注意：密码应使用 QQ 邮箱授权码。"
                )
            self._save_config(email_addr, password)
            return ToolResult(success=True, output="QQ Mail configuration saved successfully.")

        config = self._load_config()
        if not config:
            return ToolResult(
                success=False, 
                output="Error: QQ Mail not configured.",
                remedy="QQ 邮箱未配置。请先调用 setup 动作：action='setup', setup_email='您的 QQ 邮箱', setup_password='您的授权码'"
            )

        try:
            if action == "list":
                output = self._list_emails(config, kwargs.get("limit", 10))
                return ToolResult(success=True, output=output)
            elif action == "read":
                email_id = kwargs.get("email_id")
                if not email_id:
                    return ToolResult(success=False, output="Error: 'email_id' is required for 'read' action.", remedy="阅读邮件需要提供 'email_id' 指标。")
                output = self._read_email(config, email_id)
                return ToolResult(success=True, output=output)
            elif action == "send":
                output = self._send_email(config, kwargs)
                return ToolResult(success=True, output=output)
            elif action == "status":
                output = self._status(config)
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}", remedy="请检查 action 参数是否正确（list, read, send, status, setup）。")
        except Exception as e:
            error_msg = str(e)
            remedy = None
            if "authentication failed" in error_msg.lower():
                remedy = "QQ 邮箱登录失败。请检查您的授权码是否正确，以及是否开启了 IMAP 权限。"
            return ToolResult(success=False, output=f"QQ Mail Tool Error: {error_msg}", remedy=remedy)

    def _list_emails(self, config, limit):
        # QQ Mail IMAP Server
        mail = imaplib.IMAP4_SSL("imap.qq.com", 993)
        mail.login(config["email"], config["password"])
        mail.select("INBOX")

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
        mail = imaplib.IMAP4_SSL("imap.qq.com", 993)
        mail.login(config["email"], config["password"])
        mail.select("INBOX")

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

        # QQ Mail SMTP Server
        with smtplib.SMTP_SSL("smtp.qq.com", 465) as smtp:
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
        mail = imaplib.IMAP4_SSL("imap.qq.com", 993)
        mail.login(config["email"], config["password"])
        
        typ, data = mail.status("INBOX", "(MESSAGES UNSEEN)")
        mail.logout()

        if typ != "OK":
            return "Error: Failed to retrieve mailbox status."

        status_str = data[0].decode()
        
        import re
        total_match = re.search(r"MESSAGES\s+(\d+)", status_str)
        unread_match = re.search(r"UNSEEN\s+(\d+)", status_str)
        
        total = total_match.group(1) if total_match else "?"
        unread = unread_match.group(1) if unread_match else "?"
        
        return f"📧 QQ Mail Status (INBOX):\n- Total Emails: {total}\n- Unread Emails: {unread}"
