from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ensure_major_access, get_db, require_staff
from app.models import User
from app.schemas.insights import CourseOfferingRecommendation, DashboardMetrics, PlannerSelectionRequest, PlannerSelectionResponse
from app.services.insights_service import (
    all_students_view,
    course_offering_recommendations,
    dashboard_metrics,
    degree_plan_view,
    individual_student_view,
    qaa_sheet,
    save_course_offering_plan,
    saved_course_offering_plan,
    schedule_conflicts,
)

router = APIRouter(prefix='/insights', tags=['insights'])


@router.get('/{major_code}/dashboard', response_model=DashboardMetrics)
def dashboard_route(major_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    return dashboard_metrics(db, major_code)


@router.get('/{major_code}/all-students')
def all_students_route(
    major_code: str,
    simulated_courses: list[str] = Query(default=[]),
    semester_filter: str = Query(default='All Courses'),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return all_students_view(db, major_code, simulated_courses=simulated_courses, semester_filter=semester_filter)


@router.get('/{major_code}/individual/{student_id}')
def individual_student_route(
    major_code: str,
    student_id: str,
    courses: list[str] = Query(default=[]),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return individual_student_view(db, major_code, student_id, courses or None)


@router.get('/{major_code}/course-planner', response_model=list[CourseOfferingRecommendation])
def planner_route(
    major_code: str,
    graduation_threshold: int = Query(default=30),
    min_eligible_students: int = Query(default=3),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return course_offering_recommendations(db, major_code, graduation_threshold, min_eligible_students)


@router.get('/{major_code}/course-planner-state', response_model=PlannerSelectionResponse)
def planner_state_route(
    major_code: str,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return saved_course_offering_plan(db, major_code)


@router.post('/{major_code}/course-planner-state', response_model=PlannerSelectionResponse)
def save_planner_state_route(
    major_code: str,
    payload: PlannerSelectionRequest,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return save_course_offering_plan(
        db,
        major_code,
        selected_courses=payload.selected_courses,
        graduation_threshold=payload.graduation_threshold,
        min_eligible_students=payload.min_eligible_students,
        actor_user_id=user.id,
    )


@router.get('/{major_code}/qaa')
def qaa_route(
    major_code: str,
    graduating_threshold: int = Query(default=36),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return qaa_sheet(db, major_code, graduating_threshold)


@router.get('/{major_code}/schedule-conflicts')
def schedule_conflicts_route(
    major_code: str,
    target_groups: int = Query(default=10),
    max_courses_per_group: int = Query(default=10),
    min_students: int = Query(default=1),
    min_courses: int = Query(default=2),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ensure_major_access(major_code, db, user)
    return schedule_conflicts(
        db,
        major_code,
        target_groups=target_groups,
        max_courses_per_group=max_courses_per_group,
        min_students=min_students,
        min_courses=min_courses,
    )


@router.get('/{major_code}/degree-plan/{student_id}')
def degree_plan_route(major_code: str, student_id: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    ensure_major_access(major_code, db, user)
    return degree_plan_view(db, major_code, student_id)
