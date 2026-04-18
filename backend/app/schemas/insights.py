from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class GraduatingSoonStudent(BaseModel):
    student_id: str
    student_name: str


class DashboardMetrics(BaseModel):
    total_students: int
    advised_students: int
    not_advised_students: int
    progress_percent: int
    graduating_soon_unadvised: list[GraduatingSoonStudent]
    recent_activity: list[dict[str, Any]]
    credit_distribution: list[dict[str, Any]] = []


class CourseOfferingRecommendation(BaseModel):
    course: str
    priority_score: float
    currently_eligible: int
    graduating_students: int
    bottleneck_score: int
    cascading_eligible: int
    reason: str


class ScheduleConflictGroup(BaseModel):
    group_name: str
    student_count: int
    courses: list[str]
    student_ids: list[str]


class PlannerSelectionRequest(BaseModel):
    selected_courses: list[str]
    graduation_threshold: int = 30
    min_eligible_students: int = 3


class PlannerSelectionResponse(BaseModel):
    selected_courses: list[str]
    graduation_threshold: int
    min_eligible_students: int
    total_eligible: int
    total_graduating: int
    saved_at: Optional[str] = None
