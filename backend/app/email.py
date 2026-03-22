"""
Home Cloud Drive - Email utilities
"""
import smtplib
from email.message import EmailMessage
import html
from datetime import datetime

from app.config import get_settings

settings = get_settings()


def _send_email(recipient_email: str, subject: str, text_body: str, html_body: str) -> None:
    """Send a transactional email through the configured SMTP server."""
    if not settings.smtp_enabled:
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = (
        f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        if settings.smtp_from_name
        else settings.smtp_from_email
    )
    message["To"] = recipient_email

    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    if settings.smtp_use_ssl:
        smtp = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        )
    else:
        smtp = smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        )

    with smtp as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def send_password_reset_email(recipient_email: str, username: str, reset_url: str) -> None:
    """Send a password reset email with a one-time reset link."""
    if not settings.password_reset_enabled:
        raise RuntimeError("Password reset email is not configured")

    text_body = (
        f"Hello {username},\n\n"
        "We received a request to reset your Home Cloud password.\n"
        f"Use this link to choose a new password:\n\n{reset_url}\n\n"
        f"This link expires in {settings.password_reset_expire_minutes} minutes.\n"
        "If you did not request this, you can safely ignore this email.\n"
    )
    safe_username = html.escape(username)
    safe_reset_url = html.escape(reset_url, quote=True)
    html_body = (
        f"<p>Hello {safe_username},</p>"
        "<p>We received a request to reset your Home Cloud password.</p>"
        f"<p><a href=\"{safe_reset_url}\">Choose a new password</a></p>"
        f"<p>This link expires in {settings.password_reset_expire_minutes} minutes.</p>"
        "<p>If you did not request this, you can safely ignore this email.</p>"
    )

    _send_email(recipient_email, "Reset your Home Cloud password", text_body, html_body)


def send_login_alert_email(
    recipient_email: str,
    username: str,
    device_name: str,
    ip_address: str,
    login_time: datetime,
    is_suspicious: bool,
) -> None:
    """Send a new-login alert email to the account owner."""
    safe_username = html.escape(username)
    safe_device = html.escape(device_name or "Unknown device")
    safe_ip = html.escape(ip_address or "Unknown IP")
    login_time_str = login_time.strftime("%Y-%m-%d %H:%M:%S UTC")
    suspicious_line = (
        "We noticed this looks like a new device or location for your account.\n\n"
        if is_suspicious
        else ""
    )
    suspicious_html = (
        "<p><strong>This login looks like a new device or location for your account.</strong></p>"
        if is_suspicious
        else ""
    )

    text_body = (
        f"Hello {username},\n\n"
        "Your Home Cloud account just signed in.\n\n"
        f"Device: {device_name or 'Unknown device'}\n"
        f"IP address: {ip_address or 'Unknown IP'}\n"
        f"Time: {login_time_str}\n\n"
        f"{suspicious_line}"
        "If this was not you, change your password and revoke the session from Account Security.\n"
    )
    html_body = (
        f"<p>Hello {safe_username},</p>"
        "<p>Your Home Cloud account just signed in.</p>"
        f"<p><strong>Device:</strong> {safe_device}<br>"
        f"<strong>IP address:</strong> {safe_ip}<br>"
        f"<strong>Time:</strong> {html.escape(login_time_str)}</p>"
        f"{suspicious_html}"
        "<p>If this was not you, change your password and revoke the session from Account Security.</p>"
    )

    _send_email(recipient_email, "New Home Cloud sign-in", text_body, html_body)
