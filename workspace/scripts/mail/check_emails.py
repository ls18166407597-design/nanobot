import json
import os
from nanobot.tools.gmail import gmail
from nanobot.tools.qq_mail import qq_mail

def check_emails():
    report = []
    
    # Check Gmail
    try:
        g_status = gmail(action="status")
        g_unread = g_status.get("unread_count", 0)
        if g_unread > 0:
            report.append(f"📧 Gmail: {g_unread} 封未读")
    except Exception as e:
        print(f"Gmail check failed: {e}")

    # Check QQ Mail
    try:
        q_status = qq_mail(action="status")
        q_unread = q_status.get("unread_count", 0)
        if q_unread > 0:
            report.append(f"📧 QQ邮箱: {q_unread} 封未读")
    except Exception as e:
        print(f"QQ Mail check failed: {e}")

    if report:
        msg = "老板，您有新的未读邮件：\n" + "\n".join(report)
        # 这里我们可以调用 smart_send 或者直接打印，
        # 任务执行器会捕获输出并可以通过 cron 发送提醒
        print(msg)
    else:
        print("今日无新邮件。")

if __name__ == "__main__":
    check_emails()
