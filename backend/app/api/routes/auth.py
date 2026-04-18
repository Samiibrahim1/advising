from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token
from app.models import Major, UserMajorAccess
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse
from app.services.auth_service import authenticate_user

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')
    token = create_access_token(str(user.id), extra={'role': user.role})
    return TokenResponse(access_token=token)


@router.get('/me', response_model=CurrentUserResponse)
def me(user=Depends(get_current_user), db: Session = Depends(get_db)) -> CurrentUserResponse:
    access_rows = db.scalars(select(UserMajorAccess).where(UserMajorAccess.user_id == user.id)).all()
    major_codes = []
    for access in access_rows:
        major = db.get(Major, access.major_id)
        if major:
            major_codes.append(major.code)
    return CurrentUserResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role, major_codes=sorted(major_codes))
