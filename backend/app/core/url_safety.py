"""Basic SSRF guard for user-supplied outbound URLs (currently: webhook
target_url). Rejects literal IP addresses and well-known loopback hostnames
that point at the server's own loopback, private, link-local, or otherwise
non-public ranges - e.g. http://localhost, http://127.0.0.1, or a cloud
metadata endpoint like http://169.254.169.254.

Deliberately does not resolve DNS: a hostname that only later resolves to
an internal address (DNS rebinding) is not caught here. Doing so would make
every webhook save a live network call and fail closed whenever DNS is
unreachable, for a CRM-scale feature where this is not worth that cost.
"""
import ipaddress
from urllib.parse import urlsplit

_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
}


def ensure_public_target_url(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        raise ValueError("target_url must include a host.")
    if host in _BLOCKED_HOSTNAMES:
        raise ValueError("target_url may not point at a local/loopback address.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # not an IP literal - a plain hostname is allowed
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified or ip.is_multicast:
        raise ValueError("target_url may not point at a private, loopback, or link-local address.")
