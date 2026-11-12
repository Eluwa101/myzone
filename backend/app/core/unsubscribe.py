"""Per-customer unsubscribe links for marketing email.

A token is the customer's id plus a short HMAC of it, so a link can't be
guessed or edited to unsubscribe somebody else, and nothing needs storing
per email. It never expires - an unsubscribe link in a two-year-old email
still has to work."""
import base64
import hashlib
import hmac
import html
from uuid import UUID

from app.core.config import settings


def _sign(customer_hex: str) -> str:
    digest = hmac.new(settings.jwt_secret.encode(), f"unsubscribe:{customer_hex}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:22]


def make_token(customer_id: UUID) -> str:
    return f"{customer_id.hex}.{_sign(customer_id.hex)}"


def read_token(token: str) -> UUID | None:
    customer_hex, _, signature = token.partition(".")
    if len(customer_hex) != 32 or not hmac.compare_digest(signature, _sign(customer_hex)):
        return None
    try:
        return UUID(hex=customer_hex)
    except ValueError:
        return None


def page_url(token: str) -> str:
    """The human page, on the web app."""
    return f"{settings.frontend_url.rstrip('/')}/unsubscribe/{token}"


def one_click_url(token: str) -> str | None:
    """The endpoint mail apps POST to for one-click unsubscribe (RFC 8058) -
    only when the API's public address is configured."""
    if not settings.api_public_url:
        return None
    return f"{settings.api_public_url.rstrip('/')}/api/public/unsubscribe/{token}"


def headers_for(token: str) -> dict[str, str]:
    """List-Unsubscribe headers - what makes Gmail/Yahoo/Outlook show
    their own "Unsubscribe" button, and part of what they expect from
    anyone sending to their users in bulk."""
    one_click = one_click_url(token)
    if one_click:
        return {"List-Unsubscribe": f"<{one_click}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    return {"List-Unsubscribe": f"<{page_url(token)}>"}


def add_footer(body_html: str, token: str, business_name: str) -> str:
    footer = (
        '<p style="margin:24px 0 0;padding-top:12px;border-top:1px solid #e5e7eb;font-family:Arial,Helvetica,sans-serif;'
        'font-size:12px;line-height:1.5;color:#6b7280;text-align:center;">'
        f"You're receiving this email because you're a customer of {html.escape(business_name)}. "
        f'<a href="{html.escape(page_url(token))}" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a>'
        "</p>"
    )
    lowered = body_html.lower()
    at = lowered.rfind("</body>")
    return body_html[:at] + footer + body_html[at:] if at != -1 else body_html + footer
