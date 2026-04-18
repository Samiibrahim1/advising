from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


# ──────────────────────────────────────────────────────────────────
# Equivalent courses
# ──────────────────────────────────────────────────────────────────

class EquivalentCourseIn(BaseModel):
    alias_code: str
    canonical_code: str


class EquivalentCourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alias_code: str
    canonical_code: str


# ──────────────────────────────────────────────────────────────────
# Assignment types (labels like S.C.E, F.E.C)
# ──────────────────────────────────────────────────────────────────

class AssignmentTypeIn(BaseModel):
    label: str
    sort_order: int = 0


class AssignmentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    sort_order: int


# ──────────────────────────────────────────────────────────────────
# Per-student assignments
# ──────────────────────────────────────────────────────────────────

class ProgressAssignmentIn(BaseModel):
    student_id: str
    assignment_type: str
    course_code: str


class ProgressAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    assignment_type: str
    course_code: str


# ──────────────────────────────────────────────────────────────────
# Student exemptions (e.g. ARAB201)
# ──────────────────────────────────────────────────────────────────

class ExemptionIn(BaseModel):
    student_id: str
    course_code: str


class ExemptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    course_code: str


# ──────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────

class StudentProgressRow(BaseModel):
    student_id: str
    name: str
    courses: dict[str, str]       # course_code → display value
    completed_credits: float
    registered_credits: float
    remaining_credits: float
    total_credits: float
    gpa: Optional[float] = None


class ReportResponse(BaseModel):
    required: list[StudentProgressRow]
    intensive: list[StudentProgressRow]
    extra_courses: list[str]
    total_students: int
    page: int
    page_size: int


# ──────────────────────────────────────────────────────────────────
# Status / info
# ──────────────────────────────────────────────────────────────────

class ProgressReportStatus(BaseModel):
    has_report: bool
    student_count: int
    uploaded_at: Optional[str] = None


class CourseConfigStatus(BaseModel):
    has_config: bool
    required_count: int
    intensive_count: int


class DataStatus(BaseModel):
    progress_report: ProgressReportStatus
    course_config: CourseConfigStatus


class UploadProgressReportResponse(BaseModel):
    student_count: int
    row_count: int


class UploadCourseConfigResponse(BaseModel):
    required_count: int
    intensive_count: int


class BulkAssignmentResult(BaseModel):
    upserted: int
    skipped: int
    errors: list[str] = []
