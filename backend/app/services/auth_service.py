from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import User


def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
    user = session.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
