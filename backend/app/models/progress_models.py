from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.entities import TimestampMixin


class EquivalentCourse(TimestampMixin, Base):
    """Alias → canonical course code mapping per major."""

    __tablename__ = 'progress_equivalent_courses'
    __table_args__ = (UniqueConstraint('major_id', 'alias_code', name='uq_equiv_major_alias'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    alias_code: Mapped[str] = mapped_column(String(64))
    canonical_code: Mapped[str] = mapped_column(String(64))


class AssignmentType(TimestampMixin, Base):
    """Named label assignable to a student course slot (e.g. S.C.E, F.E.C) per major."""

    __tablename__ = 'progress_assignment_types'
    __table_args__ = (UniqueConstraint('major_id', 'label', name='uq_assign_type_major_label'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    label: Mapped[str] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ProgressAssignment(TimestampMixin, Base):
    """Per-student assignment of a course to a named slot (e.g. student 12345's SCE = CHEM201)."""

    __tablename__ = 'progress_assignments'
    __table_args__ = (
        UniqueConstraint('major_id', 'student_id', 'assignment_type', name='uq_prog_assign'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    major_id: Mapped[int] = mapped_column(ForeignKey('majors.id', ondelete='CASCADE'), index=True)
    student_id: Mapped[str] = mapped_column(String(64), index=True)
    assignment_type: Mapped[str] = mapped_column(String(64))
    course_code: Mapped[str] = mapped_column(String(64))
