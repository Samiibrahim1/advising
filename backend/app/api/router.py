from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import advising, audit_events, auth, backups, datasets, emails, health, imports, insights, majors, periods, progress, reports, students, templates, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(majors.router)
api_router.include_router(datasets.router)
api_router.include_router(periods.router)
api_router.include_router(students.router)
api_router.include_router(advising.router)
api_router.include_router(insights.router)
api_router.include_router(reports.router)
api_router.include_router(emails.router)
api_router.include_router(templates.router)
api_router.include_router(backups.router)
api_router.include_router(imports.router)
api_router.include_router(audit_events.router)
api_router.include_router(progress.router)
