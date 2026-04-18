from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import BackupRun, Major
from app.services.dataset_service import upload_dataset
from app.services.drive_import_service import (
    ADVISING_INDEX_FILE,
    COURSE_EXCLUSIONS_FILE,
    CURRENT_PERIOD_FILE,
    EMAIL_ROSTER_FILE,
    PERIOD_HISTORY_FILE,
    PROGRESS_FILE,
    SESSIONS_FOLDER,
    COURSES_FILE,
    _apply_session_records,
    _import_hidden_courses,
    _upsert_periods,
)
from app.services.storage import StorageService


LEGACY_DEFAULTS = {
    "courses": COURSES_FILE,
    "progress": PROGRESS_FILE,
    "email_roster": EMAIL_ROSTER_FILE,
}


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def import_legacy_snapshot(session: Session, *, major_code: str, import_root: str, user_id: Optional[int]) -> dict:
    root = Path(import_root)
    major_root = root / major_code
    if not major_root.exists():
        raise ValueError(f"Legacy folder not found: {major_root}")
    major = session.query(Major).filter(Major.code == major_code).one_or_none()
    if not major:
        raise ValueError(f"Unknown major: {major_code}")

    storage = StorageService()
    imported: dict[str, int | str] = {}
    archive_manifest: dict[str, str] = {}

    for dataset_type, filename in LEGACY_DEFAULTS.items():
        path = major_root / filename
        if not path.exists():
            continue
        file_bytes = path.read_bytes()
        archive_key = f"legacy-imports/{major_code}/{filename}"
        storage.put_bytes(archive_key, file_bytes)
        archive_manifest[dataset_type] = archive_key
        upload_dataset(session, major_code=major_code, dataset_type=dataset_type, filename=filename, content=file_bytes, user_id=user_id)
        imported[dataset_type] = filename

    current_period_payload = _read_json(major_root / CURRENT_PERIOD_FILE, None)
    if current_period_payload is not None:
        archive_manifest["current_period"] = f"legacy-imports/{major_code}/{CURRENT_PERIOD_FILE}"
        storage.put_bytes(archive_manifest["current_period"], (major_root / CURRENT_PERIOD_FILE).read_bytes())
    history_payload = _read_json(major_root / PERIOD_HISTORY_FILE, [])
    if (major_root / PERIOD_HISTORY_FILE).exists():
        archive_manifest["period_history"] = f"legacy-imports/{major_code}/{PERIOD_HISTORY_FILE}"
        storage.put_bytes(archive_manifest["period_history"], (major_root / PERIOD_HISTORY_FILE).read_bytes())
    period_map = _upsert_periods(session, major, current_period_payload, history_payload)
    imported["periods"] = len(period_map)

    exclusions_payload = _read_json(major_root / COURSE_EXCLUSIONS_FILE, {})
    hidden_count = 0
    if (major_root / COURSE_EXCLUSIONS_FILE).exists():
        archive_manifest["course_exclusions"] = f"legacy-imports/{major_code}/{COURSE_EXCLUSIONS_FILE}"
        storage.put_bytes(archive_manifest["course_exclusions"], (major_root / COURSE_EXCLUSIONS_FILE).read_bytes())
        hidden_count = _import_hidden_courses(session, major, exclusions_payload)
    imported["hidden_courses"] = hidden_count

    sessions_root = major_root / SESSIONS_FOLDER
    if sessions_root.exists():
        index_items = _read_json(sessions_root / ADVISING_INDEX_FILE, [])
        payload_by_name = {}
        for session_path in sessions_root.glob("advising_session_*.json"):
            try:
                payload_by_name[session_path.name] = json.loads(session_path.read_text(encoding="utf-8"))
            except Exception:
                continue
        session_count, selection_count = _apply_session_records(
            session,
            major=major,
            period_map=period_map,
            index_items=index_items,
            payload_by_name=payload_by_name,
            progress_label=None,
        )
        imported["sessions"] = session_count
        imported["student_selections"] = selection_count

    backup = BackupRun(
        status="completed",
        storage_key=None,
        manifest={"major_code": major_code, "source": "local_snapshot", "archive_manifest": archive_manifest, "imported": imported},
        notes="Legacy snapshot imported from local files",
    )
    session.add(backup)
    session.commit()
    return {"major_code": major_code, "source": "local_snapshot", "imported": imported, "archive_manifest": archive_manifest}
