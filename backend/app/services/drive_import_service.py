from __future__ import annotations

import json
import time
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import httplib2
from google.auth.exceptions import TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_httplib2 import AuthorizedHttp
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AdvisingPeriod,
    BackupRun,
    Bypass,
    CourseExclusion,
    HiddenCourse,
    Major,
    SessionSnapshot,
    StudentSelection,
)
from app.services.dataset_service import upload_dataset
from app.services.storage import StorageService

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
CURRENT_PERIOD_FILE = "current_period.json"
PERIOD_HISTORY_FILE = "periods_history.json"
COURSE_EXCLUSIONS_FILE = "course_exclusions.json"
EMAIL_ROSTER_FILE = "email_roster.json"
COURSES_FILE = "courses_table.xlsx"
PROGRESS_FILE = "progress_report.xlsx"
SESSIONS_FOLDER = "sessions"
ADVISING_INDEX_FILE = "advising_index.json"


@lru_cache(maxsize=1)
def _build_service(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    folder_id: str,
):
    refresh_request = Request()

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
    )
    last_error: Optional[Exception] = None
    for attempt in range(1, 6):
        try:
            creds.refresh(
                lambda url, method="GET", body=None, headers=None, timeout=120, **kwargs: refresh_request(
                    url,
                    method=method,
                    body=body,
                    headers=headers,
                    timeout=min(timeout, 20),
                    **kwargs,
                )
            )
            break
        except TransportError as exc:
            last_error = exc
            if attempt == 5:
                raise
            time.sleep(attempt * 2)
    if last_error and not creds.token:
        raise last_error
    authed_http = AuthorizedHttp(creds, http=httplib2.Http(timeout=20))
    return build("drive", "v3", http=authed_http, cache_discovery=False), folder_id


def _get_service():
    settings = get_settings()
    if not all([settings.google_client_id, settings.google_client_secret, settings.google_refresh_token, settings.google_folder_id]):
        raise ValueError("Google Drive credentials are missing. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN, and GOOGLE_FOLDER_ID.")
    return _build_service(
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_refresh_token,
        settings.google_folder_id,
    )


def _find_file(service, filename: str, parent_folder_id: str) -> Optional[str]:
    query = f"name = '{filename}' and '{parent_folder_id}' in parents and trashed = false"
    resp = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        pageSize=10,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    for item in resp.get("files", []):
        if item.get("name") == filename:
            return item.get("id")
    return None


def _list_files(service, parent_folder_id: str) -> List[dict]:
    files: List[dict] = []
    page_token: Optional[str] = None
    while True:
        resp = service.files().list(
            q=f"'{parent_folder_id}' in parents and trashed = false",
            spaces="drive",
            fields="nextPageToken, files(id, name, mimeType)",
            pageSize=1000,
            pageToken=page_token,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def _find_folder(service, folder_name: str, parent_folder_id: str) -> Optional[str]:
    query = (
        f"name = '{folder_name}' and '{parent_folder_id}' in parents "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    resp = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        pageSize=10,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    for item in resp.get("files", []):
        if item.get("name") == folder_name:
            return item.get("id")
    return None


def _download(service, file_id: str) -> bytes:
    return service.files().get_media(fileId=file_id).execute()


def _download_named(service, parent_folder_id: str, filename: str) -> Optional[bytes]:
    file_id = _find_file(service, filename, parent_folder_id)
    if not file_id:
        return None
    return _download(service, file_id)


def _major_or_error(session: Session, major_code: str) -> Major:
    major = session.scalar(select(Major).where(Major.code == major_code))
    if not major:
        raise ValueError(f"Unknown major: {major_code}")
    return major


def _archive_blob(storage: StorageService, major_code: str, filename: str, payload: bytes) -> str:
    key = f"legacy-drive-imports/{major_code}/{filename}"
    storage.put_bytes(key, payload)
    return key


def _upsert_periods(session: Session, major: Major, current_payload: Optional[dict], history_payload: list[dict]) -> Dict[str, AdvisingPeriod]:
    period_map: Dict[str, AdvisingPeriod] = {}
    combined = []
    if current_payload:
        active = dict(current_payload)
        active["is_active"] = True
        combined.append(active)
    combined.extend(history_payload or [])
    for period_data in combined:
        period_code = str(period_data.get("period_id") or "").strip()
        if not period_code:
            continue
        record = session.scalar(
            select(AdvisingPeriod).where(
                AdvisingPeriod.major_id == major.id,
                AdvisingPeriod.period_code == period_code,
            )
        )
        if not record:
            record = AdvisingPeriod(
                major_id=major.id,
                period_code=period_code,
                semester=str(period_data.get("semester", "")),
                year=int(period_data.get("year") or datetime.now().year),
                advisor_name=str(period_data.get("advisor_name", "")),
                is_active=bool(period_data.get("is_active", False)),
            )
            session.add(record)
            session.flush()
        else:
            record.semester = str(period_data.get("semester", record.semester))
            record.year = int(period_data.get("year") or record.year)
            record.advisor_name = str(period_data.get("advisor_name", record.advisor_name))
            record.is_active = bool(period_data.get("is_active", record.is_active))
        archived_at = period_data.get("archived_at")
        if archived_at:
            try:
                record.archived_at = datetime.fromisoformat(str(archived_at))
            except ValueError:
                pass
        period_map[period_code] = record
    if current_payload:
        current_code = str(current_payload.get("period_id", "")).strip()
        for code, record in period_map.items():
            record.is_active = code == current_code
    return period_map


def _import_hidden_courses(session: Session, major: Major, payload: dict) -> int:
    session.query(HiddenCourse).filter(HiddenCourse.major_id == major.id).delete()
    session.query(CourseExclusion).filter(CourseExclusion.major_id == major.id).delete()
    count = 0
    for student_id, course_codes in (payload or {}).items():
        for course_code in course_codes or []:
            session.add(HiddenCourse(major_id=major.id, student_id=str(student_id), course_code=str(course_code)))
            session.add(CourseExclusion(major_id=major.id, student_id=str(student_id), course_code=str(course_code)))
            count += 1
    return count


def _apply_session_records(
    session: Session,
    *,
    major: Major,
    period_map: Dict[str, AdvisingPeriod],
    index_items: List[dict],
    payload_by_name: Dict[str, dict],
    progress_label: Optional[str] = None,
) -> Tuple[int, int]:
    session_count = 0
    latest_by_scope: Dict[Tuple[str, str], dict] = {}
    total = len(index_items)
    for idx, item in enumerate(index_items, start=1):
        session_id = str(item.get("id", "")).strip()
        if not session_id:
            continue
        payload_name = item.get("session_file") or f"advising_session_{session_id}.json"
        payload = payload_by_name.get(payload_name)
        if not payload:
            if progress_label and idx % 25 == 0:
                print(f"[{progress_label}] {major.code} sessions {idx}/{total} imported={session_count} (missing payloads skipped)", flush=True)
            continue
        period_code = str(item.get("period_id") or "")
        period = period_map.get(period_code)
        if not period and period_map:
            period = next(iter(period_map.values()))
        if not period:
            continue
        snapshot = payload.get("snapshot") or {}
        student_payload = (snapshot.get("students") or [{}])[0]
        advised = [str(x) for x in student_payload.get("advised", [])]
        optional = [str(x) for x in student_payload.get("optional", []) if str(x) not in advised]
        repeat = [str(x) for x in student_payload.get("repeat", [])]
        existing = session.scalar(
            select(SessionSnapshot).where(
                SessionSnapshot.major_id == major.id,
                SessionSnapshot.period_id == period.id,
                SessionSnapshot.student_id == str(item.get("student_id", "")),
                SessionSnapshot.title == str(item.get("title", "")),
            )
        )
        if not existing:
            existing = SessionSnapshot(
                major_id=major.id,
                period_id=period.id,
                student_id=str(item.get("student_id", "")),
                title=str(item.get("title", "")),
                payload=payload,
                summary={"advised": advised, "optional": optional, "repeat": repeat},
                created_by_user_id=None,
            )
            session.add(existing)
        else:
            existing.payload = payload
            existing.summary = {"advised": advised, "optional": optional, "repeat": repeat}
        try:
            created_at = datetime.fromisoformat(str(item.get("created_at")))
            existing.created_at = created_at
            existing.updated_at = created_at
        except Exception:
            pass
        session_count += 1
        if progress_label and idx % 25 == 0:
            print(f"[{progress_label}] {major.code} sessions {idx}/{total} imported={session_count}", flush=True)

        scope = (str(item.get("student_id", "")), period.period_code)
        latest = latest_by_scope.get(scope)
        if latest is None or str(item.get("created_at", "")) >= str(latest.get("created_at", "")):
            latest_by_scope[scope] = {
                "student_name": str(item.get("student_name") or student_payload.get("NAME") or ""),
                "period": period,
                "selection": {
                    "advised": advised,
                    "optional": optional,
                    "repeat": repeat,
                    "note": str(student_payload.get("note", "") or ""),
                },
                "bypasses": student_payload.get("bypasses", {}) or {},
                "created_at": str(item.get("created_at", "")),
            }

    selection_count = 0
    for (student_id, _period_code), latest in latest_by_scope.items():
        period = latest["period"]
        selection = session.scalar(
            select(StudentSelection).where(
                StudentSelection.major_id == major.id,
                StudentSelection.period_id == period.id,
                StudentSelection.student_id == student_id,
            )
        )
        if not selection:
            selection = StudentSelection(
                major_id=major.id,
                period_id=period.id,
                student_id=student_id,
                student_name=latest["student_name"],
                advised=[],
                optional=[],
                repeat=[],
                note="",
            )
            session.add(selection)
        selection.student_name = latest["student_name"]
        selection.advised = latest["selection"]["advised"]
        selection.optional = [code for code in latest["selection"]["optional"] if code not in selection.advised]
        selection.repeat = latest["selection"]["repeat"]
        selection.note = latest["selection"]["note"]
        selection_count += 1

        session.query(Bypass).filter(Bypass.major_id == major.id, Bypass.student_id == student_id).delete()
        for course_code, bypass in latest["bypasses"].items():
            session.add(
                Bypass(
                    major_id=major.id,
                    student_id=student_id,
                    course_code=str(course_code),
                    note=str((bypass or {}).get("note", "")),
                    advisor_name=str((bypass or {}).get("advisor", "")),
                )
            )
    return session_count, selection_count


def _import_sessions(
    session: Session,
    major: Major,
    sessions_folder_id: Optional[str],
    period_map: Dict[str, AdvisingPeriod],
) -> Tuple[int, int]:
    if not sessions_folder_id:
        return 0, 0
    session_service = session.info.get("_drive_service")
    if session_service is None:
        return 0, 0
    session_files = {
        item.get("name"): item.get("id")
        for item in _list_files(session_service, sessions_folder_id)
        if item.get("name") and item.get("id")
    }
    index_file_id = session_files.get(ADVISING_INDEX_FILE)
    index_bytes = _download(session_service, index_file_id) if index_file_id else None
    if not index_bytes:
        return 0, 0
    index_items = json.loads(index_bytes.decode("utf-8"))
    payload_by_name: Dict[str, dict] = {}
    for name, file_id in session_files.items():
        if not name.startswith("advising_session_") or not file_id:
            continue
        try:
            payload_by_name[name] = json.loads(_download(session_service, file_id).decode("utf-8"))
        except Exception:
            continue
    return _apply_session_records(
        session,
        major=major,
        period_map=period_map,
        index_items=index_items,
        payload_by_name=payload_by_name,
        progress_label="drive-import",
    )


def import_from_google_drive(session: Session, *, major_code: str, user_id: Optional[int]) -> dict:
    major = _major_or_error(session, major_code)
    service, root_folder_id = _get_service()
    session.info["_drive_service"] = service
    storage = StorageService()

    major_folder_id = _find_folder(service, major.code, root_folder_id)
    if not major_folder_id:
        raise ValueError(f"Major folder '{major.code}' not found in Google Drive root folder.")

    imported: Dict[str, Any] = {}
    archive_manifest: Dict[str, str] = {}

    for dataset_type, filename in [
        ("courses", COURSES_FILE),
        ("progress", PROGRESS_FILE),
        ("email_roster", EMAIL_ROSTER_FILE),
    ]:
        payload = _download_named(service, major_folder_id, filename)
        if not payload:
            continue
        archive_manifest[dataset_type] = _archive_blob(storage, major.code, filename, payload)
        upload_dataset(session, major_code=major.code, dataset_type=dataset_type, filename=filename, content=payload, user_id=user_id)
        imported[dataset_type] = filename

    current_period_payload = None
    current_period_bytes = _download_named(service, major_folder_id, CURRENT_PERIOD_FILE)
    if current_period_bytes:
        archive_manifest["current_period"] = _archive_blob(storage, major.code, CURRENT_PERIOD_FILE, current_period_bytes)
        current_period_payload = json.loads(current_period_bytes.decode("utf-8"))
    history_payload: List[dict] = []
    history_bytes = _download_named(service, major_folder_id, PERIOD_HISTORY_FILE)
    if history_bytes:
        archive_manifest["period_history"] = _archive_blob(storage, major.code, PERIOD_HISTORY_FILE, history_bytes)
        history_payload = json.loads(history_bytes.decode("utf-8"))
    period_map = _upsert_periods(session, major, current_period_payload, history_payload)
    imported["periods"] = len(period_map)

    exclusions_bytes = _download_named(service, major_folder_id, COURSE_EXCLUSIONS_FILE)
    hidden_count = 0
    if exclusions_bytes:
        archive_manifest["course_exclusions"] = _archive_blob(storage, major.code, COURSE_EXCLUSIONS_FILE, exclusions_bytes)
        exclusions_payload = json.loads(exclusions_bytes.decode("utf-8"))
        hidden_count = _import_hidden_courses(session, major, exclusions_payload)
    imported["hidden_courses"] = hidden_count

    sessions_folder_id = _find_folder(service, SESSIONS_FOLDER, major_folder_id)
    if sessions_folder_id:
        session_count, selection_count = _import_sessions(session, major, sessions_folder_id, period_map)
        imported["sessions"] = session_count
        imported["student_selections"] = selection_count

    backup = BackupRun(
        status="completed",
        storage_key=None,
        manifest={"major_code": major.code, "source": "google_drive", "archive_manifest": archive_manifest, "imported": imported},
        notes="Imported directly from Google Drive",
    )
    session.add(backup)
    session.commit()
    return {"major_code": major.code, "source": "google_drive", "imported": imported, "archive_manifest": archive_manifest}
