"""Transactional email (verification links, password resets, and - later -
any customer-facing email) via Resend.

Every org shares the one verified Resend sending address (no per-tenant
domain verification required), but an email can still look branded: the
"From" display name can show the org's business name and a "Reply-To" can
point at the org's own contact email, while the underlying address stays
the platform's verified one. See auth_controller._branding_for for how
callers compute (from_name, reply_to) for a given org.

Never raises: a failed send must not break the signup/login/reset request
that triggered it (same defensive pattern as webhook dispatch and
notifications elsewhere in this app) - it logs and moves on. Without
RESEND_API_KEY configured (e.g. local dev), sends are skipped and logged
instead, so the flow is still testable without a real provider."""
import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)


def _from_address() -> str:
    """The bare email address part of settings.email_from (e.g.
    'MyShop <onboarding@resend.dev>' -> 'onboarding@resend.dev'), so a
    per-org display name can be swapped in while keeping the one verified
    sending address."""
    raw = settings.email_from
    if "<" in raw and raw.endswith(">"):
        return raw.split("<", 1)[1].rstrip(">").strip()
    return raw


def send_raw(to: str, subject: str, html: str, from_name: str | None = None, reply_to: str | None = None) -> str | None:
    """Actually calls Resend - raises on any failure (including no API key
    configured) and returns the provider's message id on success. Used by
    callers that need to know per-recipient success/failure to record it
    (e.g. the messaging batch sender's send history), as opposed to the
    fire-and-forget auth emails below, which use _send instead."""
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY is not configured.")
    resend.api_key = settings.resend_api_key
    sender = f"{from_name} <{_from_address()}>" if from_name else settings.email_from
    payload = {"from": sender, "to": [to], "subject": subject, "html": html}
    if reply_to:
        payload["reply_to"] = reply_to
    result = resend.Emails.send(payload)
    return result.get("id") if isinstance(result, dict) else None


def _send(to: str, subject: str, html: str, from_name: str | None = None, reply_to: str | None = None) -> None:
    """Fire-and-forget version for the platform's own account emails
    (verification, password reset) - a failed send must never break the
    signup/login/reset request that triggered it, so this only logs."""
    try:
        send_raw(to, subject, html, from_name=from_name, reply_to=reply_to)
    except Exception:  # noqa: BLE001 - must never raise to the caller
        logger.info("Email to %s not sent (subject: %r)", to, subject, exc_info=True)


def send_verification_email(to: str, token: str, from_name: str | None = None, reply_to: str | None = None) -> None:
    link = f"{settings.frontend_url}/verify-email?token={token}"
    _send(
        to,
        "Verify your MyShop account",
        f'<p>Welcome! Click below to verify your email and activate your account:</p>'
        f'<p><a href="{link}">{link}</a></p>'
        f'<p>This link expires in 24 hours.</p>',
        from_name=from_name,
        reply_to=reply_to,
    )


def send_password_reset_email(to: str, token: str, from_name: str | None = None, reply_to: str | None = None) -> None:
    link = f"{settings.frontend_url}/reset-password?token={token}"
    _send(
        to,
        "Reset your MyShop password",
        f'<p>Click below to choose a new password:</p>'
        f'<p><a href="{link}">{link}</a></p>'
        f"<p>This link expires in 1 hour. If you didn't request this, you can ignore this email.</p>",
        from_name=from_name,
        reply_to=reply_to,
    )


def send_google_only_account_notice(to: str, from_name: str | None = None, reply_to: str | None = None) -> None:
    _send(
        to,
        "About your MyShop account",
        "<p>This account signs in with Google - there's no password to reset. "
        'Use "Continue with Google" on the login page instead.</p>',
        from_name=from_name,
        reply_to=reply_to,
    )
