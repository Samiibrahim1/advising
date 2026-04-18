from __future__ import annotations

from app.models import progress_models  # noqa: F401 — ensures tables are registered
from app.models.entities import (
    AdvisingPeriod,
    AuditEvent,
    BackupRun,
    Bypass,
    CourseExclusion,
    DatasetVersion,
    EmailRosterEntry,
    EmailTemplate,
    ExportArtifact,
    HiddenCourse,
    Major,
    SessionSnapshot,
    StudentExemption,
    StudentSelection,
    UploadBatch,
    User,
    UserMajorAccess,
)

__all__ = [
    'AdvisingPeriod',
    'AuditEvent',
    'BackupRun',
    'Bypass',
    'CourseExclusion',
    'DatasetVersion',
    'EmailRosterEntry',
    'EmailTemplate',
    'ExportArtifact',
    'HiddenCourse',
    'Major',
    'SessionSnapshot',
    'StudentExemption',
    'StudentSelection',
    'UploadBatch',
    'User',
    'UserMajorAccess',
]
