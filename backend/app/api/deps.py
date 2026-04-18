from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, ADVISER
from app.core.security import decode_access_token
from app.db import SessionLocal
from app.models import Major, User, UserMajorAccess

bearer_scheme = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token') from exc
    user = db.get(User, int(payload['sub'])) if payload.get('sub') else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found or inactive')
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient permissions')
        return user
    return dependency


def require_admin(user: User = Depends(require_roles(ADMIN))) -> User:
    return user


def require_staff(user: User = Depends(require_roles(ADMIN, ADVISER))) -> User:
    return user


def ensure_major_access(major_code: str, db: Session, user: User) -> None:
    if user.role == ADMIN:
        return
    major = db.scalar(select(Major).where(Major.code == major_code))
    if not major:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown major')
    access = db.scalar(select(UserMajorAccess).where(UserMajorAccess.user_id == user.id, UserMajorAccess.major_id == major.id))
    if not access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Major access denied')
