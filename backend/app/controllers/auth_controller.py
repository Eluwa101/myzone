import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.email import send_password_reset_email, send_verification_email, send_google_only_account_notice
from app.core.google_auth import InvalidGoogleTokenError, verify_google_id_token
from app.core.security import create_access_token, hash_password, verify_password
from app.models.auth_token import AuthToken, AuthTokenPurpose
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, SignupRequest

VERIFY_EMAIL_TTL = timedelta(hours=24)
RESET_PASSWORD_TTL = timedelta(hours=1)


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class EmailNotVerifiedError(Exception):
    pass


class InvalidOrExpiredTokenError(Exception):
    pass


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _issue_token(db: Session, user_id, purpose: AuthTokenPurpose, ttl: timedelta) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(AuthToken(user_id=user_id, purpose=purpose, token_hash=_hash_token(raw), expires_at=datetime.now(timezone.utc) + ttl))
    db.commit()
    return raw


def _consume_token(db: Session, raw: str, purpose: AuthTokenPurpose) -> AuthToken | None:
    # expiry is compared in SQL, not after fetching the row in Python - the
    # test suite's SQLite backend doesn't round-trip timezone info on a
    # DateTime(timezone=True) column, so a naive row.expires_at compared
    # against an aware datetime.now(timezone.utc) in Python would raise
    row = (
        db.query(AuthToken)
        .filter(
            AuthToken.token_hash == _hash_token(raw),
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at >= datetime.now(timezone.utc),
        )
        .first()
    )
    if not row:
        return None
    row.used_at = datetime.now(timezone.utc)
    db.commit()
    return row


def signup(db: Session, data: SignupRequest) -> User:
    if db.query(User).filter(User.email == data.email).first():
        raise EmailAlreadyRegisteredError()

    org = Organization(name=data.org_name)
    db.add(org)
    db.flush()  # assign org.id

    user = User(
        org_id=org.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.owner,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    raw = _issue_token(db, user.id, AuthTokenPurpose.verify_email, VERIFY_EMAIL_TTL)
    send_verification_email(user.email, raw)
    return user


def login(db: Session, data: LoginRequest) -> tuple[User, str]:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        raise InvalidCredentialsError()
    if not user.email_verified:
        raise EmailNotVerifiedError()

    token = create_access_token(user.id, user.org_id)
    return user, token


def verify_email(db: Session, raw_token: str) -> tuple[User, str]:
    row = _consume_token(db, raw_token, AuthTokenPurpose.verify_email)
    if not row:
        raise InvalidOrExpiredTokenError()
    user = db.get(User, row.user_id)
    user.email_verified = True
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.org_id)
    return user, token


def resend_verification(db: Session, email: str) -> None:
    user = db.query(User).filter(User.email == email).first()
    if user and not user.email_verified:
        raw = _issue_token(db, user.id, AuthTokenPurpose.verify_email, VERIFY_EMAIL_TTL)
        send_verification_email(user.email, raw)
    # silent no-op otherwise (unknown email, or already verified) - never
    # confirm/deny whether an email is registered


def forgot_password(db: Session, email: str) -> None:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return
    if not user.hashed_password:
        send_google_only_account_notice(user.email)
        return
    raw = _issue_token(db, user.id, AuthTokenPurpose.reset_password, RESET_PASSWORD_TTL)
    send_password_reset_email(user.email, raw)


def reset_password(db: Session, raw_token: str, new_password: str) -> tuple[User, str]:
    row = _consume_token(db, raw_token, AuthTokenPurpose.reset_password)
    if not row:
        raise InvalidOrExpiredTokenError()
    user = db.get(User, row.user_id)
    user.hashed_password = hash_password(new_password)
    # clicking an emailed reset link proves control of the inbox just as
    # much as clicking a verification link would
    user.email_verified = True
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.org_id)
    return user, token


def google_auth(db: Session, credential: str) -> tuple[User, str, bool]:
    """Returns (user, access_token, is_new_user) - the last so the frontend
    can route a brand-new account into onboarding, regardless of whether
    the Google button was clicked on the login or the signup page."""
    idinfo = verify_google_id_token(credential)  # raises InvalidGoogleTokenError
    sub = idinfo["sub"]
    email = idinfo["email"]
    google_verified = bool(idinfo.get("email_verified"))

    is_new_user = False
    user = db.query(User).filter(User.google_sub == sub).first()
    if user is None:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            user.google_sub = sub
            if google_verified:
                user.email_verified = True
            db.commit()
            db.refresh(user)
        else:
            name = idinfo.get("name")
            org = Organization(name=f"{name}'s Business" if name else "My Business")
            db.add(org)
            db.flush()
            user = User(
                org_id=org.id,
                email=email,
                hashed_password=None,
                google_sub=sub,
                role=UserRole.owner,
                email_verified=google_verified,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            is_new_user = True
            if not user.email_verified:
                raw = _issue_token(db, user.id, AuthTokenPurpose.verify_email, VERIFY_EMAIL_TTL)
                send_verification_email(user.email, raw)

    token = create_access_token(user.id, user.org_id)
    return user, token, is_new_user
