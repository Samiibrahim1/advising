# google_drive.py
# Google Drive helpers with robust token refresh + update-or-create sync.
# Scope-agnostic refresh (avoids invalid_scope) and corrected files().list query.
# Added helpers: list_files_with_prefix, download_file_by_name, delete_file_by_name.
# REFACTORED: All Google API imports are lazy-loaded to prevent segfaults on Streamlit Cloud.

from __future__ import annotations

import io
from typing import Optional, List, Dict

import streamlit as st

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

_google_libs_cache = {}

def _is_drive_feature_enabled() -> bool:
    """
    Feature flag for Drive integration.
    Disable with ENABLE_GOOGLE_DRIVE=false in environment or secrets.
    """
    import os
    raw = os.getenv("ENABLE_GOOGLE_DRIVE")
    if raw is None:
        try:
            raw = st.secrets.get("google", {}).get("enabled")
        except Exception:
            raw = None
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}

def _lazy_import_google_libs():
    """
    Lazy import Google libraries only when actually needed.
    This prevents segmentation faults on Streamlit Cloud during module load.
    Returns a dict with the imported modules/classes, or raises ImportError.
    """
    global _google_libs_cache
    
    if _google_libs_cache:
        return _google_libs_cache

    if not _is_drive_feature_enabled():
        _google_libs_cache = {
            'available': False,
            'error': ImportError("Google Drive integration is disabled by ENABLE_GOOGLE_DRIVE"),
        }
        return _google_libs_cache
    
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
        from googleapiclient.errors import HttpError
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        _google_libs_cache = {
            'build': build,
            'MediaIoBaseUpload': MediaIoBaseUpload,
            'MediaIoBaseDownload': MediaIoBaseDownload,
            'HttpError': HttpError,
            'Credentials': Credentials,
            'Request': Request,
            'available': True,
        }
        return _google_libs_cache
    except ImportError as e:
        _google_libs_cache = {
            'available': False,
            'error': e,
        }
        return _google_libs_cache


def is_drive_available() -> bool:
    """Check if Google Drive libraries are available."""
    libs = _lazy_import_google_libs()
    return libs.get('available', False)


class GoogleAuthError(Exception):
    """Raised when Google auth/refresh fails (e.g. invalid_grant, invalid_scope)."""


def _secrets() -> dict:
    try:
        return st.secrets["google"]
    except Exception:
        return {}


def _get_credentials_hash() -> str:
    """Generate a hash of credentials for cache key."""
    import os
    import hashlib
    
    s = _secrets()
    client_id = s.get("client_id") or os.getenv("GOOGLE_CLIENT_ID") or ""
    client_secret = s.get("client_secret") or os.getenv("GOOGLE_CLIENT_SECRET") or ""
    refresh_token = s.get("refresh_token") or os.getenv("GOOGLE_REFRESH_TOKEN") or ""
    
    cred_string = f"{client_id}:{client_secret}:{refresh_token}"
    return hashlib.md5(cred_string.encode()).hexdigest()


def _build_credentials():
    import os
    
    libs = _lazy_import_google_libs()
    if not libs.get('available'):
        raise GoogleAuthError(
            f"Google Drive libraries not available: {libs.get('error')}"
        )
    
    Credentials = libs['Credentials']
    Request = libs['Request']
    
    s = _secrets()
    client_id = s.get("client_id") or os.getenv("GOOGLE_CLIENT_ID")
    client_secret = s.get("client_secret") or os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = s.get("refresh_token") or os.getenv("GOOGLE_REFRESH_TOKEN")

    if not (client_id and client_secret and refresh_token):
        raise GoogleAuthError(
            "Missing Google credentials in secrets. "
            "Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN in Replit Secrets."
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
    )

    try:
        creds.refresh(Request())
    except Exception as e:
        msg = str(e)
        if "invalid_grant" in msg or "Token has been expired or revoked" in msg:
            raise GoogleAuthError(
                "Google token refresh failed: invalid_grant (token expired or revoked). "
                "Re-authorize and update google.refresh_token in Streamlit Secrets."
            ) from e
        if "invalid_scope" in msg:
            raise GoogleAuthError(
                "Google token refresh failed: invalid_scope. "
                "Re-mint the refresh token using the SAME client_id/client_secret in Streamlit Secrets "
                "and grant Drive access (e.g., drive.file) — then paste the new refresh_token."
            ) from e
        raise GoogleAuthError(f"Google auth refresh failed: {e}") from e

    return creds


def _get_cached_drive_service(_cred_hash: str):
    """Internal helper to build a new Drive service."""
    libs = _lazy_import_google_libs()
    if not libs.get('available'):
        raise GoogleAuthError(
            f"Google Drive libraries not available: {libs.get('error')}"
        )
    
    build = libs['build']
    creds = _build_credentials()
    try:
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return service
    except Exception as e:
        raise GoogleAuthError(f"Failed to initialize Drive service: {e}") from e


def initialize_drive_service():
    """
    Return an authenticated Drive service. 
    Build a fresh service by default to avoid stale cross-rerun state.
    Set CACHE_DRIVE_SERVICE=1 only if you explicitly want session caching.
    """
    if not is_drive_available():
        libs = _lazy_import_google_libs()
        raise GoogleAuthError(
            f"Google Drive libraries not available: {libs.get('error')}"
        )
    
    cred_hash = _get_credentials_hash()
    import os
    use_cache = os.getenv("CACHE_DRIVE_SERVICE", "").strip().lower() in {"1", "true", "yes", "on"}

    if not use_cache:
        return _get_cached_drive_service(cred_hash)

    session_key = f"_drive_service_{cred_hash}"
    if session_key not in st.session_state:
        st.session_state[session_key] = _get_cached_drive_service(cred_hash)
    return st.session_state[session_key]


def _get_http_error_class():
    """Get HttpError class for exception handling."""
    libs = _lazy_import_google_libs()
    if libs.get('available'):
        return libs['HttpError']
    return Exception


def find_files_in_drive(service, filename: str, parent_folder_id: str, page_size: int = 20) -> List[Dict]:
    """Return exact-name matches for `filename` inside `parent_folder_id`, newest first."""
    HttpError = _get_http_error_class()
    try:
        query = f"name = '{filename}' and '{parent_folder_id}' in parents and trashed = false"
        resp = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, modifiedTime, createdTime)",
            pageSize=page_size,
            orderBy="modifiedTime desc, createdTime desc",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()
        return [f for f in resp.get("files", []) if f.get("name") == filename]
    except HttpError as e:
        raise RuntimeError(f"Drive search failed: {e}")


def find_file_in_drive(service, filename: str, parent_folder_id: str) -> Optional[str]:
    """Return the newest fileId for `filename` inside `parent_folder_id`, else None."""
    matches = find_files_in_drive(service, filename, parent_folder_id, page_size=20)
    if matches:
        return matches[0].get("id")
    return None


def download_file_from_drive(service, file_id: str) -> bytes:
    """Download file content by id."""
    libs = _lazy_import_google_libs()
    HttpError = _get_http_error_class()
    MediaIoBaseDownload = libs.get('MediaIoBaseDownload')
    
    try:
        req = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()
    except HttpError as e:
        raise RuntimeError(f"Drive download failed: {e}")


def sync_file_with_drive(
    service,
    file_content: bytes,
    drive_file_name: str,
    mime_type: str,
    parent_folder_id: str,
) -> str:
    """
    Create or replace a file by name inside `parent_folder_id`.
    Returns the fileId. Includes retry logic for SSL errors.
    """
    import time
    import ssl
    
    libs = _lazy_import_google_libs()
    HttpError = _get_http_error_class()
    MediaIoBaseUpload = libs.get('MediaIoBaseUpload')
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype=mime_type, resumable=False)
            body = {"name": drive_file_name, "parents": [parent_folder_id]}

            matches = find_files_in_drive(service, drive_file_name, parent_folder_id, page_size=20)
            file_id = matches[0].get("id") if matches else None
            if file_id:
                updated = service.files().update(
                    fileId=file_id,
                    media_body=media,
                    body={"name": drive_file_name},
                    supportsAllDrives=True,
                ).execute()
                kept_id = updated.get("id", file_id)
                # If duplicate same-name files exist, keep the newest updated file and remove stale copies.
                for duplicate in matches[1:]:
                    dup_id = duplicate.get("id")
                    if dup_id and dup_id != kept_id:
                        try:
                            service.files().delete(fileId=dup_id, supportsAllDrives=True).execute()
                        except HttpError:
                            pass
                return kept_id
            else:
                created = service.files().create(
                    body=body,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
                return created.get("id")
                
        except ssl.SSLError as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                raise RuntimeError(f"Drive sync failed after {max_retries} retries (SSL error): {e}")
        except HttpError as e:
            raise RuntimeError(f"Drive sync failed: {e}")


def list_files_with_prefix(service, parent_folder_id: str, prefix: str, page_size: int = 100) -> List[Dict]:
    """
    List files in folder whose name contains `prefix`, newest first.
    Returns list of dicts with keys: id, name, modifiedTime.
    """
    HttpError = _get_http_error_class()
    try:
        query = f"name contains '{prefix}' and '{parent_folder_id}' in parents and trashed = false"
        resp = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, modifiedTime)",
            pageSize=page_size,
            orderBy="modifiedTime desc",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()
        return resp.get("files", [])
    except HttpError as e:
        raise RuntimeError(f"Drive list failed: {e}")


def download_file_by_name(service, parent_folder_id: str, filename: str) -> Optional[bytes]:
    """Find by exact name in folder and download."""
    fid = find_file_in_drive(service, filename, parent_folder_id)
    if not fid:
        return None
    return download_file_from_drive(service, fid)


def delete_file_by_name(service, parent_folder_id: str, filename: str) -> bool:
    """Delete a file by name if it exists. Returns True if deleted or not present."""
    HttpError = _get_http_error_class()
    try:
        fid = find_file_in_drive(service, filename, parent_folder_id)
        if not fid:
            return True
        service.files().delete(fileId=fid, supportsAllDrives=True).execute()
        return True
    except HttpError:
        return False


def delete_file_from_drive(service, file_id: str) -> bool:
    """Delete a file by its file ID. Returns True if deleted successfully."""
    HttpError = _get_http_error_class()
    try:
        service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
        return True
    except HttpError:
        return False


def find_folder_by_name(service, folder_name: str, parent_folder_id: str) -> Optional[str]:
    """Find a folder by name inside parent_folder_id. Returns folder ID or None."""
    HttpError = _get_http_error_class()
    try:
        query = f"name = '{folder_name}' and '{parent_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        resp = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
            pageSize=10,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()
        for f in resp.get("files", []):
            if f.get("name") == folder_name:
                return f.get("id")
        return None
    except HttpError as e:
        raise RuntimeError(f"Drive folder search failed: {e}")


def create_folder(service, folder_name: str, parent_folder_id: str) -> str:
    """Create a folder inside parent_folder_id. Returns the new folder ID."""
    HttpError = _get_http_error_class()
    try:
        body = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id]
        }
        folder = service.files().create(
            body=body,
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return folder.get("id")
    except HttpError as e:
        raise RuntimeError(f"Drive folder creation failed: {e}")


def get_or_create_folder(service, folder_name: str, parent_folder_id: str) -> str:
    """Get existing folder ID or create it if it doesn't exist. Returns folder ID."""
    folder_id = find_folder_by_name(service, folder_name, parent_folder_id)
    if folder_id:
        return folder_id
    return create_folder(service, folder_name, parent_folder_id)


@st.cache_data(ttl=3600)
def get_major_folder_id(_service, major: str, root_folder_id: str) -> str:
    """
    Get or create a major-specific folder inside the root folder.
    Cached for 1 hour to avoid repeated API calls.
    
    Args:
        _service: Drive service (prefixed with _ to exclude from cache key)
        major: Major name (e.g., 'PBHL', 'SPTH-New', 'SPTH-Old')
        root_folder_id: Root folder ID from secrets
    
    Returns:
        Folder ID for the major-specific folder
    """
    return get_or_create_folder(_service, major, root_folder_id)
