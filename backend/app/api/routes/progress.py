from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import ensure_major_access, get_db, require_admin, require_staff
from app.models import User
from app.schemas.common import MessageResponse
from app.schemas.progress import (
    AssignmentTypeIn,
    AssignmentTypeOut,
    BulkAssignmentResult,
    CourseConfigStatus,
    DataStatus,
    EquivalentCourseIn,
    EquivalentCourseOut,
    ExemptionIn,
    ExemptionOut,
    ProgressAssignmentIn,
    ProgressAssignmentOut,
    ProgressReportStatus,
    ReportResponse,
    UploadCourseConfigResponse,
    UploadProgressReportResponse,
)
from app.services.progress_service import (
    bulk_upsert_assignments_from_excel,
    create_assignment_type,
    delete_assignment,
    delete_assignment_type,
    export_report_excel,
    generate_report,
    get_data_status,
    list_assignment_types,
    list_assignments,
    list_equivalents,
    list_exemptions,
    preview_progress_upload,
    push_progress_to_advising,
    remove_exemption,
    replace_equivalents,
    reset_all_assignments,
    set_exemption,
    upload_course_config,
    upload_progress_report,
    upsert_assignment,
)

router = APIRouter(prefix='/progress', tags=['progress'])

_PROGRESS_TEMPLATES: dict[str, dict] = {
    'progress-report': {
        'filename': 'progress_report_template.xlsx',
        'sheet': 'Progress Report',
        'columns': ['ID', 'NAME', 'Course Code', 'Grade', 'Year', 'Semester'],
        'rows': [
            ['20210001', 'John Doe', 'PBHL201', 'A', 2024, 'Fall'],
            ['20210001', 'John Doe', 'PBHL301', 'B+', 2024, 'Fall'],
            ['20210002', 'Jane Smith', 'PBHL201', 'A-', 2025, 'Spring'],
            ['20210002', 'Jane Smith', 'PBHL310', 'CR', 2025, 'Spring'],
        ],
    },
    'course-config': {
        'filename': 'course_config_template.xlsx',
        'sheet': 'Course Config',
        'columns': ['Course', 'Type', 'Credits', 'PassingGrades', 'FromSemester', 'FromYear', 'ToSemester', 'ToYear'],
        'rows': [
            ['PBHL201', 'required', 3, 'A+,A,A-,B+,B,B-,C+,C,CR', '', '', '', ''],
            ['PBHL301', 'required', 3, 'A+,A,A-,B+,B,B-,C+,C,CR', '', '', '', ''],
            ['PBHL401', 'intensive', 3, 'A+,A,A-,B+,B', 'Fall', 2023, '', ''],
        ],
    },
    'elective-assignments': {
        'filename': 'elective_assignments_template.xlsx',
        'sheet': 'Assignments',
        'columns': ['Student ID', 'Assignment Type', 'Course Code'],
        'rows': [
            ['20210001', 'SCE', 'PBHL450'],
            ['20210002', 'SCE', 'PBHL460'],
            ['20210003', 'FEC', 'PBHL470'],
        ],
    },
}


@router.get('/templates/{template_name}')
def download_progress_template(
    template_name: str,
    user: User = Depends(require_staff),
) -> Response:
    """Download a sample XLSX template for a progress upload type."""
    import pandas as pd
    tmpl = _PROGRESS_TEMPLATES.get(template_name)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f'No template available for: {template_name}')
    buf = io.BytesIO()
    df = pd.DataFrame(tmpl['rows'], columns=tmpl['columns'])
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=tmpl['sheet'], index=False)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{tmpl["filename"]}"'},
    )


# ──────────────────────────────────────────────────────────────────
# Status
# ──────────────────────────────────────────────────────────────────

@router.get('/{major_code}/status', response_model=DataStatus)
def get_status(
    major_code: str,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return get_data_status(db, major_code)


# ──────────────────────────────────────────────────────────────────
# File uploads (admin only)
# ──────────────────────────────────────────────────────────────────

@router.post('/{major_code}/upload/progress-report/preview')
def preview_progress(
    major_code: str,
    file: UploadFile,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Parse a progress report and return a diff summary without saving."""
    ensure_major_access(major_code, db, user)
    content = file.file.read()
    try:
        return preview_progress_upload(db, major_code, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post('/{major_code}/upload/progress-report', response_model=UploadProgressReportResponse)
def upload_progress(
    major_code: str,
    file: UploadFile,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    content = file.file.read()
    try:
        result = upload_progress_report(db, major_code, file.filename or 'upload', content, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.post('/{major_code}/upload/course-config', response_model=UploadCourseConfigResponse)
def upload_config(
    major_code: str,
    file: UploadFile,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    content = file.file.read()
    try:
        result = upload_course_config(db, major_code, file.filename or 'upload', content, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


# ──────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────

@router.get('/{major_code}/report', response_model=ReportResponse)
def get_report(
    major_code: str,
    show_all_grades: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: str = Query(''),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    try:
        return generate_report(db, major_code, show_all_grades, page, page_size, search)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/{major_code}/report/export')
def export_report(
    major_code: str,
    show_all_grades: bool = Query(False),
    collapse_mode: bool = Query(False),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    try:
        xlsx_bytes = export_report_excel(db, major_code, show_all_grades, collapse_mode)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="progress_{major_code}.xlsx"'},
    )


@router.post('/{major_code}/push-to-advising')
def push_to_advising(
    major_code: str,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    try:
        result = push_progress_to_advising(db, major_code, user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


# ──────────────────────────────────────────────────────────────────
# Equivalent courses
# ──────────────────────────────────────────────────────────────────

@router.get('/{major_code}/equivalents', response_model=list[EquivalentCourseOut])
def get_equivalents(
    major_code: str,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return list_equivalents(db, major_code)


@router.put('/{major_code}/equivalents', response_model=list[EquivalentCourseOut])
def set_equivalents(
    major_code: str,
    pairs: list[EquivalentCourseIn],
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    rows = replace_equivalents(db, major_code, [p.model_dump() for p in pairs])
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


# ──────────────────────────────────────────────────────────────────
# Assignment types (labels)
# ──────────────────────────────────────────────────────────────────

@router.get('/{major_code}/assignment-types', response_model=list[AssignmentTypeOut])
def get_assignment_types(
    major_code: str,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return list_assignment_types(db, major_code)


@router.post('/{major_code}/assignment-types', response_model=AssignmentTypeOut, status_code=201)
def add_assignment_type(
    major_code: str,
    body: AssignmentTypeIn,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    try:
        at = create_assignment_type(db, major_code, body.label, body.sort_order)
        db.commit()
        db.refresh(at)
        return at
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete('/{major_code}/assignment-types/{type_id}', response_model=MessageResponse)
def remove_assignment_type(
    major_code: str,
    type_id: int,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    try:
        delete_assignment_type(db, major_code, type_id)
        db.commit()
        return MessageResponse(message='Assignment type deleted.')
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# ──────────────────────────────────────────────────────────────────
# Per-student assignments
# ──────────────────────────────────────────────────────────────────

@router.get('/{major_code}/assignments', response_model=list[ProgressAssignmentOut])
def get_assignments(
    major_code: str,
    student_id: Optional[str] = Query(None),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return list_assignments(db, major_code, student_id)


@router.put('/{major_code}/assignments', response_model=ProgressAssignmentOut)
def save_assignment(
    major_code: str,
    body: ProgressAssignmentIn,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    try:
        pa = upsert_assignment(db, major_code, body.student_id, body.assignment_type, body.course_code)
        db.commit()
        db.refresh(pa)
        return pa
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete('/{major_code}/assignments/one', response_model=MessageResponse)
def remove_assignment(
    major_code: str,
    student_id: str = Query(...),
    assignment_type: str = Query(...),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    try:
        delete_assignment(db, major_code, student_id, assignment_type)
        db.commit()
        return MessageResponse(message='Assignment deleted.')
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete('/{major_code}/assignments', response_model=MessageResponse)
def reset_assignments(
    major_code: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    n = reset_all_assignments(db, major_code)
    db.commit()
    return MessageResponse(message=f'Reset {n} assignment(s).')


@router.post('/{major_code}/upload/elective-assignments', response_model=BulkAssignmentResult)
def upload_elective_assignments(
    major_code: str,
    file: UploadFile,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    content = file.file.read()
    try:
        result = bulk_upsert_assignments_from_excel(db, major_code, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return result


# ──────────────────────────────────────────────────────────────────
# Exemptions (e.g. ARAB201)
# ──────────────────────────────────────────────────────────────────

@router.get('/{major_code}/exemptions', response_model=list[ExemptionOut])
def get_exemptions(
    major_code: str,
    student_id: Optional[str] = Query(None),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return list_exemptions(db, major_code, student_id)


@router.post('/{major_code}/exemptions', response_model=ExemptionOut, status_code=201)
def add_exemption(
    major_code: str,
    body: ExemptionIn,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    result = set_exemption(db, major_code, body.student_id, body.course_code)
    db.commit()
    db.refresh(result)
    return result


@router.delete('/{major_code}/exemptions', response_model=MessageResponse)
def delete_exemption(
    major_code: str,
    body: ExemptionIn,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    remove_exemption(db, major_code, body.student_id, body.course_code)
    db.commit()
    return MessageResponse(message='Exemption removed.')
