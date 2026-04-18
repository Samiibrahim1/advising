from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import ensure_major_access, get_db, require_staff
from app.models import AdvisingPeriod, User
from sqlalchemy import select as sa_select
from app.schemas.advising import (
    BulkRestoreRequest,
    BypassRequest,
    ExclusionRequest,
    ExclusionSummary,
    HiddenCoursesRequest,
    RecommendationResponse,
    SaveSelectionRequest,
    SessionSummary,
)
from app.schemas.common import MessageResponse
from app.services.student_service import (
    bulk_restore_sessions,
    clear_period_selections,
    delete_session,
    list_exclusions,
    list_sessions,
    recommended_courses,
    remove_bypass,
    replace_exclusions,
    replace_hidden_courses,
    restore_all_sessions,
    restore_latest_session,
    save_selection,
    set_bypass,
)

router = APIRouter(prefix='/advising', tags=['advising'])


@router.post('/selection', response_model=MessageResponse)
def save_selection_route(payload: SaveSelectionRequest, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(payload.major_code, db, user)
    try:
        save_selection(db, major_code=payload.major_code, period_code=payload.period_code, student_id=payload.student_id, student_name=payload.student_name, payload=payload.selection, user_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message='Selection saved.')


@router.get('/sessions/{major_code}', response_model=list[SessionSummary])
def list_sessions_route(major_code: str, period_code: Optional[str] = None, student_id: Optional[str] = None, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    sessions = list_sessions(db, major_code, period_code=period_code, student_id=student_id)
    # Build a period_id -> period_code lookup for all relevant periods
    period_ids = {item.period_id for item in sessions}
    period_map: dict[int, str] = {}
    if period_ids:
        rows = db.execute(sa_select(AdvisingPeriod.id, AdvisingPeriod.period_code).where(AdvisingPeriod.id.in_(period_ids))).all()
        period_map = {row[0]: row[1] for row in rows}
    return [SessionSummary(id=item.id, title=item.title, student_id=item.student_id, student_name=item.payload.get('student_name', item.student_id), period_code=period_map.get(item.period_id), created_at=item.created_at, summary=item.summary) for item in sessions]


@router.post('/sessions/{major_code}/{period_code}/{student_id}/restore', response_model=MessageResponse)
def restore_session_route(major_code: str, period_code: str, student_id: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    try:
        restore_latest_session(db, major_code, period_code, student_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MessageResponse(message='Latest session restored.')


@router.post('/sessions/{major_code}/snapshot/{snapshot_id}/restore', response_model=MessageResponse)
def restore_snapshot_route(major_code: str, snapshot_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    """Restore a specific snapshot by ID to the currently active period."""
    ensure_major_access(major_code, db, user)
    from app.models import SessionSnapshot
    snapshot = db.get(SessionSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail='Snapshot not found.')
    active_period = db.scalar(sa_select(AdvisingPeriod).where(
        AdvisingPeriod.major_id == snapshot.major_id,
        AdvisingPeriod.is_active.is_(True),
    ))
    if not active_period:
        raise HTTPException(status_code=400, detail='No active advising period to restore into.')
    from app.schemas.advising import SelectionPayload
    period_code = active_period.period_code
    payload = SelectionPayload(**snapshot.payload.get('selection', {}))
    student_name = snapshot.payload.get('student_name', snapshot.student_id)
    save_selection(db, major_code=major_code, period_code=period_code, student_id=snapshot.student_id, student_name=student_name, payload=payload, user_id=user.id, create_snapshot=False)
    return MessageResponse(message='Session restored to active period.')


@router.delete('/sessions/{major_code}/snapshot/{snapshot_id}', response_model=MessageResponse)
def delete_session_route(major_code: str, snapshot_id: int, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    try:
        delete_session(db, major_code, snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MessageResponse(message='Session deleted.')


@router.post('/sessions/restore-all', response_model=MessageResponse)
def restore_all_sessions_route(payload: BulkRestoreRequest, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(payload.major_code, db, user)
    restored = restore_all_sessions(db, major_code=payload.major_code, period_code=payload.period_code, user_id=user.id)
    return MessageResponse(message=f'Restored sessions for {restored} students.')


@router.post('/sessions/bulk-restore', response_model=MessageResponse)
def bulk_restore_sessions_route(payload: BulkRestoreRequest, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(payload.major_code, db, user)
    restored = bulk_restore_sessions(db, major_code=payload.major_code, period_code=payload.period_code, student_ids=payload.student_ids, user_id=user.id)
    return MessageResponse(message=f'Restored sessions for {restored} students.')


@router.delete('/selection/{major_code}/{period_code}', response_model=MessageResponse)
def clear_selection_route(major_code: str, period_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    deleted = clear_period_selections(db, major_code, period_code)
    return MessageResponse(message=f'Cleared {deleted} selection records.')


@router.get('/recommendations/{major_code}/{student_id}', response_model=RecommendationResponse)
def recommendations_route(major_code: str, student_id: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    return RecommendationResponse(courses=recommended_courses(db, major_code, student_id))


@router.post('/bypasses', response_model=MessageResponse)
def set_bypass_route(payload: BypassRequest, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(payload.major_code, db, user)
    set_bypass(db, major_code=payload.major_code, student_id=payload.student_id, course_code=payload.course_code, note=payload.note, advisor_name=payload.advisor_name or user.full_name)
    return MessageResponse(message='Bypass saved.')


@router.delete('/bypasses/{major_code}/{student_id}/{course_code}', response_model=MessageResponse)
def remove_bypass_route(major_code: str, student_id: str, course_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    remove_bypass(db, major_code, student_id, course_code)
    return MessageResponse(message='Bypass removed.')


@router.post('/hidden-courses', response_model=list[str])
def hidden_courses_route(payload: HiddenCoursesRequest, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(payload.major_code, db, user)
    return replace_hidden_courses(db, payload.major_code, payload.student_id, payload.course_codes)


@router.post('/exclusions', response_model=dict[str, list[str]])
def exclusions_route(payload: ExclusionRequest, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(payload.major_code, db, user)
    return replace_exclusions(db, payload.major_code, payload.student_ids, payload.course_codes)


@router.get('/exclusions/{major_code}', response_model=list[ExclusionSummary])
def list_exclusions_route(major_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    return list_exclusions(db, major_code)


@router.post('/{major_code}/placements/upload')
def upload_placements_route(
    major_code: str,
    file: UploadFile,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Upload a bulk intensive-placement report (student_id + placement_course).

    Derives and applies course exclusions per student based on the prerequisite
    chain among intensive courses.  Students not in the file are untouched.
    """
    ensure_major_access(major_code, db, user)
    content = file.file.read()
    try:
        from app.services.placement_service import bulk_placement_from_file
        result = bulk_placement_from_file(db, major_code, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Store the uploaded file as a versioned dataset so Settings can show "Current File"
    try:
        from app.services.dataset_service import upload_dataset
        upload_dataset(db, major_code=major_code, dataset_type='placements',
                       filename=file.filename or 'placements.xlsx', content=content, user_id=user.id)
    except Exception:
        pass  # non-fatal — versioning failure must not break the upload
    return result
