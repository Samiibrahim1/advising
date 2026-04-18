from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    major_access: Mapped[list['UserMajorAccess']] = relationship(back_populates='user', cascade='all, delete-orphan')

    @property
    def major_codes(self) -> list[str]:
        return sorted([acc.major.code for acc in self.major_access])


class Major(TimestampMixin, Base):
    __tablename__ = 'majors'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    smtp_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    smtp_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)

    datasets: Mapped[list['DatasetVersion']] = relationship(back_populates='major', cascade='all, delete-orphan')
    periods: Mapped[list['AdvisingPeriod']] = relationship(back_populates='major', cascade='all, delete-orphan')


class UserMajorAccess(TimestampMixin, Base):
    __tablename__ = 'user_major_access'
    __table_args__ = (UniqueConstraint('user_id', 'major_id', name='uq_user_major_access'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'))

    user: Mapped['User'] = relationship(back_populates='major_access')
    major: Mapped['Major'] = relationship()


class UploadBatch(TimestampMixin, Base):
    __tablename__ = 'upload_batches'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'))
    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    status: Mapped[str] = mapped_column(String(32), default='processed')
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)


class DatasetVersion(TimestampMixin, Base):
    __tablename__ = 'dataset_versions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    dataset_type: Mapped[str] = mapped_column(String(64), index=True)
    version_label: Mapped[str] = mapped_column(String(128))
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parsed_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    major: Mapped['Major'] = relationship(back_populates='datasets')


class AdvisingPeriod(TimestampMixin, Base):
    __tablename__ = 'advising_periods'
    __table_args__ = (UniqueConstraint('major_id', 'period_code', name='uq_advising_period_scope'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    period_code: Mapped[str] = mapped_column(String(128), index=True)
    semester: Mapped[str] = mapped_column(String(32))
    year: Mapped[int] = mapped_column(Integer)
    advisor_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('dataset_versions.id', ondelete='SET NULL'), nullable=True, default=None
    )
    progress_dataset_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('dataset_versions.id', ondelete='SET NULL'), nullable=True, default=None
    )
    config_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('dataset_versions.id', ondelete='SET NULL'), nullable=True, default=None
    )

    major: Mapped['Major'] = relationship(back_populates='periods')


class StudentSelection(TimestampMixin, Base):
    __tablename__ = 'student_selections'
    __table_args__ = (UniqueConstraint('major_id', 'period_id', 'student_id', name='uq_student_selection_scope'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey('advising_periods.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True)
    student_name: Mapped[str] = mapped_column(String(255))
    advised: Mapped[list] = mapped_column(JSON, default=list)
    optional: Mapped[list] = mapped_column(JSON, default=list)
    repeat: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(Text, default='')
    last_saved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))


class SessionSnapshot(TimestampMixin, Base):
    __tablename__ = 'session_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey('advising_periods.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))


class CourseExclusion(TimestampMixin, Base):
    __tablename__ = 'course_exclusions'
    __table_args__ = (UniqueConstraint('major_id', 'student_id', 'course_code', name='uq_course_exclusion_scope'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True)
    course_code: Mapped[str] = mapped_column(String(64), index=True)


class HiddenCourse(TimestampMixin, Base):
    __tablename__ = 'hidden_courses'
    __table_args__ = (UniqueConstraint('major_id', 'student_id', 'course_code', name='uq_hidden_course_scope'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True)
    course_code: Mapped[str] = mapped_column(String(64), index=True)


class Bypass(TimestampMixin, Base):
    __tablename__ = 'bypasses'
    __table_args__ = (UniqueConstraint('major_id', 'student_id', 'course_code', name='uq_bypass_scope'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True)
    course_code: Mapped[str] = mapped_column(String(64), index=True)
    note: Mapped[str] = mapped_column(Text, default='')
    advisor_name: Mapped[str] = mapped_column(String(255), default='')


class StudentExemption(TimestampMixin, Base):
    """Per-student exemption from a specific course (e.g. ARAB201).

    When a student is marked exempt, the course remains visible in required lists
    but the adviser can assign a substitute course via the progress assignments
    mechanism (using ``assignment_type`` equal to the exempted course code).
    """
    __tablename__ = 'student_exemptions'
    __table_args__ = (UniqueConstraint('major_id', 'student_id', 'course_code', name='uq_student_exemption_scope'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True)
    course_code: Mapped[str] = mapped_column(String(64), index=True)


class EmailRosterEntry(TimestampMixin, Base):
    __tablename__ = 'email_roster_entries'
    __table_args__ = (UniqueConstraint('major_id', 'student_id', name='uq_email_roster_scope'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True)
    student_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255))


class EmailTemplate(TimestampMixin, Base):
    __tablename__ = 'email_templates'
    __table_args__ = (UniqueConstraint('major_id', 'template_key', name='uq_email_template_scope'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[Optional[int]] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), nullable=True, index=True)
    template_key: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default='')
    subject_template: Mapped[str] = mapped_column(Text, default='Academic Advising - {major}')
    body_template: Mapped[str] = mapped_column(Text, default='Dear {student_name},')
    include_summary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ExportArtifact(TimestampMixin, Base):
    __tablename__ = 'export_artifacts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    period_id: Mapped[Optional[int]] = mapped_column(ForeignKey('advising_periods.id', ondelete='SET NULL'), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class BackupRun(TimestampMixin, Base):
    __tablename__ = 'backup_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AuditEvent(TimestampMixin, Base):
    __tablename__ = 'audit_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    actor: Mapped[Optional['User']] = relationship('User', foreign_keys=[actor_user_id])
