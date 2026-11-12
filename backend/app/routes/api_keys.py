import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.api_keys import generate_key
from app.core.database import get_db
from app.core.security import get_session_user
from app.models.api_key import ApiKey
from app.models.user import User

# Managing keys needs a real login, not an API key - so a leaked key can't
# be used to mint more keys or hide itself.
router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])

MAX_ACTIVE_KEYS = 20


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyOut(BaseModel):
    id: UUID
    name: str
    prefix: str
    created_at: datetime.datetime
    last_used_at: datetime.datetime | None
    revoked_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyOut):
    # the only time the full key is ever returned
    key: str


@router.get("", response_model=list[ApiKeyOut])
def list_keys(db: Session = Depends(get_db), current_user: User = Depends(get_session_user)):
    return db.query(ApiKey).filter(ApiKey.org_id == current_user.org_id).order_by(ApiKey.created_at.desc()).all()


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(data: ApiKeyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_session_user)):
    active = db.query(ApiKey).filter(ApiKey.org_id == current_user.org_id, ApiKey.revoked_at.is_(None)).count()
    if active >= MAX_ACTIVE_KEYS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"You can have at most {MAX_ACTIVE_KEYS} active keys - revoke one first.")
    key, prefix, key_hash = generate_key()
    api_key = ApiKey(org_id=current_user.org_id, created_by=current_user.id, name=data.name.strip(), prefix=prefix, key_hash=key_hash)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return ApiKeyCreated(**ApiKeyOut.model_validate(api_key).model_dump(), key=key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(key_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_session_user)):
    api_key = db.query(ApiKey).filter(ApiKey.org_id == current_user.org_id, ApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")
    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
