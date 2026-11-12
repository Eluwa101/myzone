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


def sending_domain() -> str:
    """The verified domain every address this app sends from lives on (the
    part after the @ in settings.email_from)."""
    return _from_address().rsplit("@", 1)[-1]


def send_raw(
    to: str,
    subject: str,
    html: str,
    from_name: str | None = None,
    reply_to: str | None = None,
    from_address: str | None = None,
    headers: dict[str, str] | None = None,
) -> str | None:
    """Actually calls Resend - raises on any failure (including no API key
    configured) and returns the provider's message id on success. Used by
    callers that need to know per-recipient success/failure to record it
    (e.g. the messaging batch sender's send history), as opposed to the
    fire-and-forget auth emails below, which use _send instead.
    from_address overrides the platform's own address - it must be on the
    verified sending domain (see sending_domain)."""
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY is not configured.")
    resend.api_key = settings.resend_api_key
    if from_name:
        sender = f"{from_name} <{from_address or _from_address()}>"
    else:
        sender = from_address or settings.email_from
    payload = {"from": sender, "to": [to], "subject": subject, "html": html}
    if reply_to:
        payload["reply_to"] = reply_to
    if headers:
        payload["headers"] = headers
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


def _date(when) -> str:
    return when.strftime("%d %B %Y")


def send_account_closure_scheduled(to: str, business: str, scheduled_for, requested_by: str) -> None:
    import html as _html

    _send(
        to,
        f"Your MyShop account for {business} will be closed",
        f"<p>{_html.escape(requested_by)} asked to close the MyShop account for <b>{_html.escape(business)}</b>.</p>"
        f"<p>On <b>{_date(scheduled_for)}</b> all of its data - customers, sales, orders, notes, messages and everything else - "
        "will be permanently deleted. Until then the account is read-only: you can still sign in and export your data "
        "(Data &rarr; Export customers).</p>"
        f'<p>Changed your mind? An owner can cancel in <a href="{settings.frontend_url}/settings">Settings</a> any time before then.</p>',
    )


def send_account_closure_cancelled(to: str, business: str, cancelled_by: str) -> None:
    import html as _html

    _send(
        to,
        f"Your MyShop account for {business} is staying open",
        f"<p>{_html.escape(cancelled_by)} cancelled the closure of <b>{_html.escape(business)}</b>. Nothing will be deleted, "
        "and the account can be changed again as normal.</p>",
    )


def send_account_deleted(to: str, business: str) -> None:
    import html as _html

    _send(
        to,
        f"Your MyShop account for {business} has been deleted",
        f"<p>As requested, the MyShop account for <b>{_html.escape(business)}</b> has been closed and all of its data permanently "
        "deleted. Thank you for using MyShop.</p>",
    )
