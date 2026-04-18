from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import ensure_major_access, get_db, require_staff
from app.models import User
from fastapi import Query

from app.services.insights_service import build_all_advised_report, build_individual_report, build_qaa_report, build_schedule_conflicts_report
from app.services.student_service import export_student_report

router = APIRouter(prefix='/reports', tags=['reports'])


@router.get('/{major_code}/student/{student_id}')
def student_report_route(major_code: str, student_id: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    filename, payload = export_student_report(db, major_code, student_id)
    headers = {'Content-Disposition': f'attachment; filename={filename}'}
    return Response(content=payload, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)


@router.get('/{major_code}/individual/{student_id}')
def individual_compact_report_route(
    major_code: str,
    student_id: str,
    courses: list[str] = Query(default=[]),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    filename, payload = build_individual_report(db, major_code, student_id, courses or None)
    headers = {'Content-Disposition': f'attachment; filename={filename}'}
    return Response(content=payload, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)


@router.get('/{major_code}/all-advised')
def all_advised_report_route(major_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    filename, payload = build_all_advised_report(db, major_code)
    headers = {'Content-Disposition': f'attachment; filename={filename}'}
    return Response(content=payload, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)


@router.get('/{major_code}/qaa')
def qaa_report_route(
    major_code: str,
    graduating_threshold: int = Query(default=36),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    filename, payload = build_qaa_report(db, major_code, graduating_threshold)
    headers = {'Content-Disposition': f'attachment; filename={filename}'}
    return Response(content=payload, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)


@router.get('/{major_code}/schedule-conflicts')
def schedule_conflict_report_route(
    major_code: str,
    target_groups: int = Query(default=10),
    max_courses_per_group: int = Query(default=10),
    min_students: int = Query(default=1),
    min_courses: int = Query(default=2),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    filename, payload = build_schedule_conflicts_report(
        db,
        major_code,
        target_groups=target_groups,
        max_courses_per_group=max_courses_per_group,
        min_students=min_students,
        min_courses=min_courses,
    )
    headers = {'Content-Disposition': f'attachment; filename={filename}'}
    return Response(content=payload, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)
