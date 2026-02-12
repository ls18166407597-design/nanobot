import imaplib
import json
import os
from pathlib import Path


def _resolve_home_dir() -> Path:
    env_home = os.getenv("NANOBOT_HOME", "").strip()
    if env_home:
        return Path(env_home).expanduser().resolve()
    # workspace/skills/mail/scripts/check_emails.py -> project root/.home
    return (Path(__file__).resolve().parents[4] / ".home").resolve()


def _read_cfg(home_dir: Path, filename: str) -> dict:
    cfg_path = home_dir / "tool_configs" / filename
    if not cfg_path.exists():
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _count_unread(imap_host: str, email_user: str, email_pass: str, mailbox: str = "INBOX") -> int:
    mail = imaplib.IMAP4_SSL(imap_host, timeout=15)
    try:
        mail.login(email_user, email_pass)
        mail.select(mailbox)
        status, response = mail.search(None, "UNSEEN")
        if status != "OK":
            raise RuntimeError(f"search failed: {status}")
        return len(response[0].split()) if response and response[0] else 0
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def check_emails() -> int:
    home_dir = _resolve_home_dir()
    lines: list[str] = []

    # Gmail
    gmail_cfg = _read_cfg(home_dir, "gmail_config.json")
    if gmail_cfg.get("email") and gmail_cfg.get("password"):
        try:
            unread = _count_unread("imap.gmail.com", gmail_cfg["email"], gmail_cfg["password"])
            lines.append(f"Gmail 未读: {unread}")
        except Exception as e:
            lines.append(f"Gmail 检查失败: {e}")
    else:
        lines.append("Gmail 未配置")

    # QQ Mail
    qq_cfg = _read_cfg(home_dir, "qq_mail_config.json")
    if qq_cfg.get("email") and qq_cfg.get("password"):
        try:
            unread = _count_unread("imap.qq.com", qq_cfg["email"], qq_cfg["password"])
            lines.append(f"QQ邮箱 未读: {unread}")
        except Exception as e:
            lines.append(f"QQ邮箱 检查失败: {e}")
    else:
        lines.append("QQ邮箱 未配置")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(check_emails())
