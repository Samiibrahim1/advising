from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import ensure_major_access, get_db, require_admin, require_staff
from app.models import User
from app.schemas.admin import TemplateResponse, TemplateUpdateRequest
from app.schemas.advising import TemplatePreviewResponse
from app.services.email_service import build_student_email
from app.services.template_service import list_templates, upsert_template

router = APIRouter(prefix='/templates', tags=['templates'])


@router.get('', response_model=list[TemplateResponse])
def list_templates_route(major_code: Optional[str] = None, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    if major_code:
        ensure_major_access(major_code, db, user)
    return list_templates(db, major_code)


@router.post('', response_model=TemplateResponse)
def upsert_template_route(payload: TemplateUpdateRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return upsert_template(
            db,
            major_code=payload.major_code,
            template_key=payload.template_key,
            display_name=payload.display_name,
            description=payload.description,
            subject_template=payload.subject_template,
            body_template=payload.body_template,
            include_summary=payload.include_summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/preview', response_model=TemplatePreviewResponse)
def preview_template_route(
    major_code: str,
    student_id: str,
    template_key: str = Query(default='default'),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    try:
        preview = build_student_email(db, major_code=major_code, student_id=student_id, template_key=template_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TemplatePreviewResponse(
        template_key=str(preview['template_key']),
        subject=str(preview['subject']),
        preview_body=str(preview['preview_body']),
        variables=preview['variables'],
    )
