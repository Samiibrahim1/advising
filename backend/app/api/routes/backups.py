from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models import BackupRun, User
from app.schemas.admin import BackupRunResponse

router = APIRouter(prefix='/backups', tags=['backups'])


@router.get('', response_model=list[BackupRunResponse])
def list_backups(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(BackupRun).order_by(BackupRun.created_at.desc())))


@router.post('/trigger', response_model=BackupRunResponse)
def trigger_backup(user: User = Depends(require_admin)):
    """Run a manual backup immediately. Creates a pg_dump + storage manifest."""
    from app.services.backup_job import run_backup
    try:
        run = run_backup(triggered_by=user.full_name or user.email)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f'Backup failed: {exc}') from exc
    return run


@router.post('/{backup_id}/restore')
def restore_from_backup(backup_id: int, user: User = Depends(require_admin)):
    """Restore the database from a completed backup. This overwrites the current database."""
    from app.services.backup_job import restore_backup
    try:
        result = restore_backup(backup_id, triggered_by=user.full_name or user.email)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f'Restore failed: {exc}') from exc
    return result
