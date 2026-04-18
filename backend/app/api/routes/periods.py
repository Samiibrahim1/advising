from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import ensure_major_access, get_db, require_admin, require_staff
from app.models import User
from app.schemas.admin import PeriodCreateRequest, PeriodResponse
from app.services.audit import log_event
from app.services.period_service import activate_period, create_period, current_period, delete_period, list_periods

router = APIRouter(prefix='/periods', tags=['periods'])


@router.get('/{major_code}', response_model=list[PeriodResponse])
def list_periods_route(major_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    return list_periods(db, major_code)


@router.get('/{major_code}/current', response_model=Optional[PeriodResponse])
def current_period_route(major_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    return current_period(db, major_code)


@router.post('', response_model=PeriodResponse)
def create_period_route(payload: PeriodCreateRequest, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    try:
        period = create_period(db, major_code=payload.major_code, semester=payload.semester, year=payload.year, advisor_name=payload.advisor_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_event(db, user.id, 'period.created', 'period', str(period.id), {'major_code': payload.major_code, 'period_code': period.period_code})
    db.commit()
    return period


@router.post('/{period_code}/activate', response_model=PeriodResponse)
def activate_period_route(period_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    try:
        period = activate_period(db, period_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    log_event(db, user.id, 'period.activated', 'period', str(period.id), {'period_code': period.period_code})
    db.commit()
    return period


@router.delete('/{major_code}/{period_code}', status_code=204)
def delete_period_route(major_code: str, period_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    try:
        delete_period(db, major_code, period_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    log_event(db, user.id, 'period.deleted', 'period', period_code, {'major_code': major_code, 'period_code': period_code})
    db.commit()
