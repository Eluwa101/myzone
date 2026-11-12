from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class SignupRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8)


class SignupResult(BaseModel):
    status: str = "verification_required"
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # only meaningful on /api/auth/google - whether signing in just created
    # a brand-new account, so the frontend knows to route into onboarding
    is_new_user: bool = False


class UserOut(BaseModel):
    id: UUID
    org_id: UUID
    email: EmailStr
    role: UserRole
    email_verified: bool
    is_platform_admin: bool = False
    # true while an admin is inside another business's account
    admin_session: bool = False

    model_config = {"from_attributes": True}


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class GoogleAuthRequest(BaseModel):
    credential: str
