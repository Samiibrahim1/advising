from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import AdvisingPeriod, DatasetVersion, Major


def get_or_create_default_period_code(major_code: str, semester: str, year: int, advisor_name: str) -> str:
    normalized = advisor_name.lower().replace(' ', '-') or 'advisor'
    return f'{major_code.lower()}-{semester.lower()}-{year}-{normalized}'


def list_periods(session: Session, major_code: str) -> list[AdvisingPeriod]:
    major = session.scalar(select(Major).where(Major.code == major_code))
    if not major:
        return []
    return list(session.scalars(select(AdvisingPeriod).where(AdvisingPeriod.major_id == major.id).order_by(AdvisingPeriod.created_at.desc())))


def _active_version_id(session: Session, major_id: int, dataset_type: str) -> int | None:
    dv = session.scalar(
        select(DatasetVersion).where(
            DatasetVersion.major_id == major_id,
            DatasetVersion.dataset_type == dataset_type,
            DatasetVersion.is_active.is_(True),
        )
    )
    return dv.id if dv else None


def create_period(session: Session, *, major_code: str, semester: str, year: int, advisor_name: str) -> AdvisingPeriod:
    major = session.scalar(select(Major).where(Major.code == major_code))
    if not major:
        raise ValueError(f'Unknown major: {major_code}')

    session.execute(update(AdvisingPeriod).where(AdvisingPeriod.major_id == major.id).values(is_active=False))

    period = AdvisingPeriod(
        major_id=major.id,
        period_code=get_or_create_default_period_code(major.code, semester, year, advisor_name),
        semester=semester,
        year=year,
        advisor_name=advisor_name,
        is_active=True,
        progress_version_id=_active_version_id(session, major.id, 'progress_report'),
        progress_dataset_version_id=_active_version_id(session, major.id, 'progress'),
        config_version_id=_active_version_id(session, major.id, 'course_config'),
    )
    session.add(period)
    session.commit()
    session.refresh(period)
    return period


def _restore_dataset(session: Session, major_id: int, dataset_type: str, version_id: int | None) -> None:
    """Deactivate all versions of *dataset_type* for the major, then activate the given version."""
    if version_id is None:
        return
    session.execute(
        update(DatasetVersion)
        .where(DatasetVersion.major_id == major_id, DatasetVersion.dataset_type == dataset_type)
        .values(is_active=False)
    )
    session.execute(
        update(DatasetVersion)
        .where(DatasetVersion.id == version_id)
        .values(is_active=True)
    )


def activate_period(session: Session, period_code: str) -> AdvisingPeriod:
    period = session.scalar(select(AdvisingPeriod).where(AdvisingPeriod.period_code == period_code))
    if not period:
        raise ValueError(f'Unknown period: {period_code}')
    session.execute(update(AdvisingPeriod).where(AdvisingPeriod.major_id == period.major_id).values(is_active=False))
    period.is_active = True

    # Restore all snapshotted datasets to the versions captured when this period was created
    _restore_dataset(session, period.major_id, 'progress_report', period.progress_version_id)
    _restore_dataset(session, period.major_id, 'progress', period.progress_dataset_version_id)
    _restore_dataset(session, period.major_id, 'course_config', period.config_version_id)

    session.commit()
    session.refresh(period)
    return period


def current_period(session: Session, major_code: str) -> Optional[AdvisingPeriod]:
    major = session.scalar(select(Major).where(Major.code == major_code))
    if not major:
        return None
    period = session.scalar(select(AdvisingPeriod).where(AdvisingPeriod.major_id == major.id, AdvisingPeriod.is_active.is_(True)))
    if period:
        return period
    return None


def delete_period(session: Session, major_code: str, period_code: str) -> None:
    major = session.scalar(select(Major).where(Major.code == major_code))
    if not major:
        raise ValueError(f'Unknown major: {major_code}')
    period = session.scalar(select(AdvisingPeriod).where(AdvisingPeriod.period_code == period_code, AdvisingPeriod.major_id == major.id))
    if not period:
        raise ValueError(f'Unknown period: {period_code}')
    session.delete(period)
    session.commit()


def archive_period(session: Session, period_code: str) -> AdvisingPeriod:
    period = session.scalar(select(AdvisingPeriod).where(AdvisingPeriod.period_code == period_code))
    if not period:
        raise ValueError(f'Unknown period: {period_code}')
    period.is_active = False
    period.archived_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(period)
    return period
