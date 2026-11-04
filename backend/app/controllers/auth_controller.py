from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, SignupRequest


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def signup(db: Session, data: SignupRequest) -> tuple[User, str]:
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
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, org.id)
    return user, token


def login(db: Session, data: LoginRequest) -> tuple[User, str]:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise InvalidCredentialsError()

    token = create_access_token(user.id, user.org_id)
    return user, token
