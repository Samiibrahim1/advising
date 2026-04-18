from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.config import get_settings
from app.models import User
from app.services.drive_import_service import import_from_google_drive
from app.services.import_service import import_legacy_snapshot
from app.services.snapshot_export_service import export_google_drive_snapshot

router = APIRouter(prefix='/imports', tags=['imports'])


@router.post('/legacy/{major_code}')
def import_legacy_route(major_code: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        return import_legacy_snapshot(db, major_code=major_code, import_root=settings.legacy_imports_path, user_id=admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/google-drive/{major_code}')
def import_google_drive_route(major_code: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return import_from_google_drive(db, major_code=major_code, user_id=admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/snapshot-import/{major_code}')
def import_snapshot_route(major_code: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        return import_legacy_snapshot(db, major_code=major_code, import_root=settings.legacy_snapshot_export_path, user_id=admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/snapshot-export/{major_code}')
def export_snapshot_route(major_code: str, admin: User = Depends(require_admin)):
    try:
        return export_google_drive_snapshot(major_code=major_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
