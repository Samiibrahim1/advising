from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmailTemplate, Major


def list_templates(session: Session, major_code: Optional[str] = None) -> list[EmailTemplate]:
    if major_code is None:
        return list(session.scalars(select(EmailTemplate).where(EmailTemplate.major_id.is_(None)).order_by(EmailTemplate.template_key.asc())))
    major = session.scalar(select(Major).where(Major.code == major_code))
    if not major:
        return []
    return list(session.scalars(select(EmailTemplate).where((EmailTemplate.major_id == major.id) | (EmailTemplate.major_id.is_(None))).order_by(EmailTemplate.template_key.asc())))


def upsert_template(session: Session, *, major_code: Optional[str], template_key: str, display_name: str, description: str, subject_template: str, body_template: str, include_summary: bool) -> EmailTemplate:
    major_id = None
    if major_code:
        major = session.scalar(select(Major).where(Major.code == major_code))
        if not major:
            raise ValueError(f'Unknown major: {major_code}')
        major_id = major.id
    template = session.scalar(select(EmailTemplate).where(EmailTemplate.major_id == major_id, EmailTemplate.template_key == template_key))
    if not template:
        template = EmailTemplate(major_id=major_id, template_key=template_key, display_name=display_name, description=description, subject_template=subject_template, body_template=body_template, include_summary=include_summary)
        session.add(template)
    else:
        template.display_name = display_name
        template.description = description
        template.subject_template = subject_template
        template.body_template = body_template
        template.include_summary = include_summary
    session.commit()
    session.refresh(template)
    return template
