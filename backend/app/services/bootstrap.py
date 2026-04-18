from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.roles import ADMIN, ADVISER
from app.core.security import hash_password
from app.models import EmailTemplate, Major, User, UserMajorAccess

DEFAULT_MAJORS = [
    ('PBHL', 'Public Health'),
    ('SPTH-New', 'Speech Therapy New'),
    ('SPTH-Old', 'Speech Therapy Old'),
    ('NURS', 'Nursing'),
]

DEFAULT_TEMPLATES = {
    'default': {
        'display_name': 'Standard Advising',
        'description': 'Standard advising recommendations with course details',
        'subject_template': 'Academic Advising - {major}',
        'body_template': 'Dear {student_name},\n\nBased on your academic progress and requirements, here are your recommended courses for {semester} {year}:',
        'include_summary': True,
    },
    'probation': {
        'display_name': 'Academic Probation',
        'description': 'Recovery-focused recommendations',
        'subject_template': 'Academic Advising Recovery Plan - {major}',
        'body_template': 'Dear {student_name},\n\nYour current standing requires immediate attention. The following courses are essential to improve your academic progress:',
        'include_summary': True,
    },
}


def seed_defaults(session: Session) -> None:
    for code, name in DEFAULT_MAJORS:
        existing = session.scalar(select(Major).where(Major.code == code))
        if not existing:
            session.add(Major(code=code, name=name))

    admin = session.scalar(select(User).where(User.email == 'admin@example.com'))
    if not admin:
        admin = User(email='admin@example.com', full_name='System Admin', password_hash=hash_password('admin1234'), role=ADMIN)
        session.add(admin)
        session.flush()

    adviser = session.scalar(select(User).where(User.email == 'adviser@example.com'))
    if not adviser:
        adviser = User(email='adviser@example.com', full_name='Default Adviser', password_hash=hash_password('adviser1234'), role=ADVISER)
        session.add(adviser)
        session.flush()

    majors = session.scalars(select(Major)).all()
    for user in (admin, adviser):
        for major in majors:
            access = session.scalar(
                select(UserMajorAccess).where(UserMajorAccess.user_id == user.id, UserMajorAccess.major_id == major.id)
            )
            if not access:
                session.add(UserMajorAccess(user_id=user.id, major_id=major.id))

    for template_key, template_data in DEFAULT_TEMPLATES.items():
        existing = session.scalar(select(EmailTemplate).where(EmailTemplate.major_id.is_(None), EmailTemplate.template_key == template_key))
        if not existing:
            session.add(EmailTemplate(major_id=None, template_key=template_key, **template_data))

    session.commit()
