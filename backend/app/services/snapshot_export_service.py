from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from app.core.config import get_settings
from app.services.drive_import_service import (
    ADVISING_INDEX_FILE,
    COURSE_EXCLUSIONS_FILE,
    COURSES_FILE,
    CURRENT_PERIOD_FILE,
    EMAIL_ROSTER_FILE,
    PERIOD_HISTORY_FILE,
    PROGRESS_FILE,
    SESSIONS_FOLDER,
    _download,
    _download_named,
    _find_folder,
    _get_service,
    _list_files,
)


def export_google_drive_snapshot(*, major_code: str) -> dict:
    settings = get_settings()
    service, root_folder_id = _get_service()
    major_folder_id = _find_folder(service, major_code, root_folder_id)
    if not major_folder_id:
        raise ValueError(f"Major folder '{major_code}' not found in Google Drive root folder.")

    export_root = Path(settings.legacy_snapshot_export_path).resolve()
    major_root = export_root / major_code
    sessions_root = major_root / SESSIONS_FOLDER
    sessions_root.mkdir(parents=True, exist_ok=True)

    exported: Dict[str, int | List[str] | str] = {"datasets": [], "session_files": 0}
    for filename in [COURSES_FILE, PROGRESS_FILE, EMAIL_ROSTER_FILE, CURRENT_PERIOD_FILE, PERIOD_HISTORY_FILE, COURSE_EXCLUSIONS_FILE]:
        payload = _download_named(service, major_folder_id, filename)
        if not payload:
            continue
        (major_root / filename).write_bytes(payload)
        if filename.endswith((".xlsx", ".json")):
            cast_list = exported.setdefault("datasets", [])
            if isinstance(cast_list, list):
                cast_list.append(filename)

    sessions_folder_id = _find_folder(service, SESSIONS_FOLDER, major_folder_id)
    if sessions_folder_id:
        session_items = _list_files(service, sessions_folder_id)
        for item in session_items:
            name = item.get("name")
            file_id = item.get("id")
            if not name or not file_id:
                continue
            if name == ADVISING_INDEX_FILE or name.startswith("advising_session_"):
                (sessions_root / name).write_bytes(_download(service, file_id))
                if name.startswith("advising_session_"):
                    exported["session_files"] = int(exported["session_files"]) + 1

    exported["snapshot_root"] = str(major_root)
    return {"major_code": major_code, "snapshot_root": str(major_root), "exported": exported}
