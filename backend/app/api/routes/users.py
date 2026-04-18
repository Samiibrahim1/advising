from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.roles import STAFF_ROLES
from app.core.security import hash_password
from app.models import Major, User, UserMajorAccess
from app.schemas.admin import UserCreateRequest, UserResponse, UserUpdateRequest
from app.services.audit import log_event

router = APIRouter(prefix='/users', tags=['users'])


@router.get('', response_model=list[UserResponse])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


@router.post('', response_model=UserResponse)
def create_user(payload: UserCreateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> User:
    if payload.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail='Invalid role')
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail='Email already exists')
    user = User(email=payload.email, full_name=payload.full_name, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.flush()
    for code in payload.major_codes:
        major = db.scalar(select(Major).where(Major.code == code))
        if major:
            db.add(UserMajorAccess(user_id=user.id, major_id=major.id))
    log_event(db, admin.id, 'user.created', 'user', str(user.id), {'role': user.role, 'major_codes': payload.major_codes})
    db.commit()
    db.refresh(user)
    return user


@router.patch('/{user_id}/deactivate', response_model=UserResponse)
def deactivate_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail='Cannot deactivate yourself')
    user.is_active = False
    log_event(db, admin.id, 'user.deactivated', 'user', str(user.id), {})
    db.commit()
    db.refresh(user)
    return user


@router.patch('/{user_id}/activate', response_model=UserResponse)
def activate_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    user.is_active = True
    log_event(db, admin.id, 'user.activated', 'user', str(user.id), {})
    db.commit()
    db.refresh(user)
    return user


@router.patch('/{user_id}', response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        if payload.role not in STAFF_ROLES:
            raise HTTPException(status_code=400, detail='Invalid role')
        user.role = payload.role
    if payload.new_password is not None and payload.new_password.strip():
        user.password_hash = hash_password(payload.new_password)
    if payload.major_codes is not None:
        db.query(UserMajorAccess).filter(UserMajorAccess.user_id == user.id).delete()
        for code in payload.major_codes:
            major = db.scalar(select(Major).where(Major.code == code))
            if major:
                db.add(UserMajorAccess(user_id=user.id, major_id=major.id))
    log_event(db, admin.id, 'user.updated', 'user', str(user.id), {'major_codes': payload.major_codes})
    db.commit()
    db.refresh(user)
    return user


@router.delete('/{user_id}')
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail='Cannot delete yourself')
    log_event(db, admin.id, 'user.deleted', 'user', str(user.id), {'email': user.email})
    db.delete(user)
    db.commit()
    return {'deleted': True}
