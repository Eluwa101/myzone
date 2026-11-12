from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.controllers import auth_controller
from app.core.database import get_db
from app.core.google_auth import InvalidGoogleTokenError
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignupRequest,
    SignupResult,
    Token,
    UserOut,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResult, status_code=status.HTTP_201_CREATED)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    try:
        user = auth_controller.signup(db, data)
    except auth_controller.EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")
    return SignupResult(email=user.email)


@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    try:
        _, token = auth_controller.login(db, data)
    except auth_controller.InvalidCredentialsError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    except auth_controller.EmailNotVerifiedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "email_not_verified", "message": "Please verify your email before logging in."},
        )
    return Token(access_token=token)


@router.post("/verify-email", response_model=Token)
def verify_email(data: VerifyEmailRequest, db: Session = Depends(get_db)):
    try:
        _, token = auth_controller.verify_email(db, data.token)
    except auth_controller.InvalidOrExpiredTokenError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This link is invalid or has expired.")
    return Token(access_token=token)


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
def resend_verification(data: ResendVerificationRequest, db: Session = Depends(get_db)):
    auth_controller.resend_verification(db, data.email)
    return {"status": "ok"}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    auth_controller.forgot_password(db, data.email)
    return {"status": "ok"}


@router.post("/reset-password", response_model=Token)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        _, token = auth_controller.reset_password(db, data.token, data.new_password)
    except auth_controller.InvalidOrExpiredTokenError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This link is invalid or has expired.")
    return Token(access_token=token)


@router.post("/google", response_model=Token)
def google_auth(data: GoogleAuthRequest, db: Session = Depends(get_db)):
    try:
        _, token, is_new_user = auth_controller.google_auth(db, data.credential)
    except InvalidGoogleTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return Token(access_token=token, is_new_user=is_new_user)


@router.get("/me", response_model=UserOut)
def me(request: Request, current_user: User = Depends(get_current_user)):
    from app.core.security import is_platform_admin

    return UserOut(
        **UserOut.model_validate(current_user).model_dump(exclude={"is_platform_admin", "admin_session"}),
        is_platform_admin=is_platform_admin(current_user),
        admin_session=bool(getattr(request.state, "admin_session", False)),
    )
