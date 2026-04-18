from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditEvent


def log_event(session: Session, actor_user_id: Optional[int], event_type: str, entity_type: str, entity_id: str, payload: Optional[dict] = None) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
    )
    session.add(event)
    session.flush()
    return event
