"""Verifies the ID token Google's "Sign in with Google" button hands the
frontend (via Google Identity Services) - no server-side redirect/secret
needed, just checking the token's signature and audience against Google's
own public keys."""
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import settings


class InvalidGoogleTokenError(Exception):
    pass


def verify_google_id_token(credential: str) -> dict:
    if not settings.google_oauth_client_id:
        raise InvalidGoogleTokenError("Google sign-in is not configured for this app yet.")
    try:
        return id_token.verify_oauth2_token(credential, google_requests.Request(), settings.google_oauth_client_id)
    except ValueError as e:
        raise InvalidGoogleTokenError("Invalid or expired Google credential.") from e
