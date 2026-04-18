from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin, require_staff
from app.models import Major, User
from app.schemas.admin import MajorCreateRequest, MajorResponse, MajorUpdateRequest
from app.services.audit import log_event

router = APIRouter(prefix='/majors', tags=['majors'])


@router.get('', response_model=list[MajorResponse])
def list_majors(_: User = Depends(require_staff), db: Session = Depends(get_db)) -> list[Major]:
    return list(db.scalars(select(Major).order_by(Major.code.asc())))


@router.post('', response_model=MajorResponse)
def create_major(payload: MajorCreateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> Major:
    existing = db.scalar(select(Major).where(Major.code == payload.code))
    if existing:
        raise HTTPException(status_code=400, detail='Major already exists')
    major = Major(code=payload.code, name=payload.name)
    db.add(major)
    db.flush()
    log_event(db, admin.id, 'major.created', 'major', str(major.id), {'code': major.code})
    db.commit()
    db.refresh(major)
    return major


@router.put('/{code}', response_model=MajorResponse)
def update_major(code: str, payload: MajorUpdateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> Major:
    major = db.scalar(select(Major).where(Major.code == code))
    if not major:
        raise HTTPException(status_code=404, detail='Major not found')
    if payload.name is not None:
        major.name = payload.name
    if payload.smtp_email is not None:
        major.smtp_email = payload.smtp_email or None
    if payload.smtp_password is not None:
        major.smtp_password = payload.smtp_password or None
    log_event(db, admin.id, 'major.updated', 'major', str(major.id), {'code': major.code})
    db.commit()
    db.refresh(major)
    return major


@router.get('/{code}/smtp-password')
def reveal_smtp_password(code: str, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    major = db.scalar(select(Major).where(Major.code == code))
    if not major:
        raise HTTPException(status_code=404, detail='Major not found')
    return {'smtp_password': major.smtp_password or ''}


@router.delete('/{code}')
def delete_major(code: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    major = db.scalar(select(Major).where(Major.code == code))
    if not major:
        raise HTTPException(status_code=404, detail='Major not found')
    log_event(db, admin.id, 'major.deleted', 'major', str(major.id), {'code': major.code, 'name': major.name})
    db.delete(major)
    db.commit()
    return {'deleted': True}
