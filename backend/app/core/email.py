"""Transactional email (verification links, password resets) via Resend.

Never raises: a failed send must not break the signup/login/reset request
that triggered it (same defensive pattern as webhook dispatch and
notifications elsewhere in this app) - it logs and moves on. Without
RESEND_API_KEY configured (e.g. local dev), sends are skipped and logged
instead, so the flow is still testable without a real provider."""
import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send(to: str, subject: str, html: str) -> None:
    if not settings.resend_api_key:
        logger.info("RESEND_API_KEY not configured - skipping email to %s (subject: %r)", to, subject)
        return
    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({"from": settings.email_from, "to": [to], "subject": subject, "html": html})
    except Exception:  # noqa: BLE001 - a failed send must never break the caller's request
        logger.exception("Failed to send email to %s", to)


def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.frontend_url}/verify-email?token={token}"
    _send(
        to,
        "Verify your MyShop account",
        f'<p>Welcome! Click below to verify your email and activate your account:</p>'
        f'<p><a href="{link}">{link}</a></p>'
        f'<p>This link expires in 24 hours.</p>',
    )


def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.frontend_url}/reset-password?token={token}"
    _send(
        to,
        "Reset your MyShop password",
        f'<p>Click below to choose a new password:</p>'
        f'<p><a href="{link}">{link}</a></p>'
        f"<p>This link expires in 1 hour. If you didn't request this, you can ignore this email.</p>",
    )


def send_google_only_account_notice(to: str) -> None:
    _send(
        to,
        "About your MyShop account",
        "<p>This account signs in with Google - there's no password to reset. "
        'Use "Continue with Google" on the login page instead.</p>',
    )
