"""
Home Cloud Drive - Email utilities
"""
from datetime import datetime
import html
import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.config import get_settings

settings = get_settings()


def _send_email(recipient_email: str, subject: str, text_body: str, html_body: str) -> None:
    """Send a transactional email through the configured Resend API."""
    if not settings.email_delivery_enabled:
        raise RuntimeError("Resend email delivery is not configured")

    from_value = (
        f"{settings.resend_from_name} <{settings.resend_from_email}>"
        if settings.resend_from_name
        else settings.resend_from_email
    )
    payload = {
        "from": from_value,
        "to": [recipient_email],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        settings.resend_api_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "home-cloud/1.0",
        },
    )

    try:
        with urllib_request.urlopen(req, timeout=settings.resend_timeout_seconds) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Resend API rejected the email send with status {response.status}")
    except urllib_error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Resend API request failed with status {exc.code}: {error_body}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Failed to reach Resend API: {exc.reason}") from exc


def send_password_reset_email(recipient_email: str, username: str, reset_url: str) -> None:
    """Send a password reset email with a one-time reset link."""
    if not settings.password_reset_enabled:
        raise RuntimeError("Password reset email delivery is not configured")

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
