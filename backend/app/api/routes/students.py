from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import ensure_major_access, get_db, require_staff
from app.models import User
from app.schemas.advising import CourseCatalogItem, StudentEligibilityResponse, StudentSearchItem
from app.services.student_service import course_catalog, search_students, student_eligibility

router = APIRouter(prefix='/students', tags=['students'])


@router.get('/{major_code}/search', response_model=list[StudentSearchItem])
def search_students_route(major_code: str, query: Optional[str] = Query(default=None), user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    return search_students(db, major_code, query)


@router.get('/{major_code}/catalog', response_model=list[CourseCatalogItem])
def course_catalog_route(major_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    return course_catalog(db, major_code)


@router.get('/{major_code}/{student_id}', response_model=StudentEligibilityResponse)
def student_eligibility_route(major_code: str, student_id: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    try:
        return student_eligibility(db, major_code, student_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
