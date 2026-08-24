import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote


def send_password_reset_email(recipient: str, token: str) -> None:
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM_EMAIL")
    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL are required for password reset delivery")

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    reset_url = f"{frontend_url}/forgot-password?token={quote(token)}"

    message = EmailMessage()
    message["Subject"] = "Reset your RxOS password"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your RxOS account. "
        f"Open this link within one hour: {reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    message.add_alternative(
        "<p>A password reset was requested for your RxOS account.</p>"
        f'<p><a href="{html.escape(reset_url, quote=True)}">Reset your password</a></p>'
        "<p>This link expires in one hour. If you did not request this, ignore this email.</p>",
        subtype="html",
    )

    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=10) as server:
            if username:
                server.login(username, password or "")
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            if username:
                server.login(username, password or "")
            server.send_message(message)
