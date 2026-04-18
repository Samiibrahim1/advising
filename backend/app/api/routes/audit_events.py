from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, require_admin
from app.models import AuditEvent, User
from app.schemas.admin import AuditEventResponse

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=list[AuditEventResponse])
def list_audit_events(
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=200, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = (
        select(AuditEvent)
        .options(joinedload(AuditEvent.actor))
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    if event_type:
        stmt = stmt.where(AuditEvent.event_type.startswith(event_type))
    return list(db.scalars(stmt))
