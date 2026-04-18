from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import ensure_major_access, get_db, require_staff
from app.models import User
from app.schemas.common import MessageResponse
from app.services.audit import log_event
from app.services.email_service import send_student_email

router = APIRouter(prefix='/emails', tags=['emails'])


@router.post('/{major_code}/{student_id}', response_model=MessageResponse)
def send_email_route(major_code: str, student_id: str, template_key: str = Query(default='default'), user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    result = send_student_email(db, major_code=major_code, student_id=student_id, template_key=template_key, adviser_email=user.email)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    log_event(db, user.id, 'email.sent', 'student', student_id, {'major_code': major_code, 'template_key': template_key, 'recipient': result.get('recipient'), 'cc': user.email})
    db.commit()
    return MessageResponse(message=result['message'])
