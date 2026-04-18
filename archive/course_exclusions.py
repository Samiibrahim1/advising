# course_exclusions.py
# Per-student course exclusions (hidden courses), persisted per MAJOR to Google Drive.

from __future__ import annotations
import json
from typing import Dict, List, Union

import streamlit as st
from advising_utils import log_error, log_info

def _get_drive_module():
    """Lazy loader for google_drive module to avoid import-time side effects."""
    import google_drive as gd
    return gd


def _filename() -> str:
    return "course_exclusions.json"


def _load_from_drive() -> Dict[str, List[str]]:
    """Fetch exclusions map from Drive; returns {} if not found / any issue."""
    import os
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        major = st.session_state.get("current_major", "DEFAULT")
        
        # Safe access to root folder_id
        root_folder_id = ""
        try:
            if "google" in st.secrets:
                root_folder_id = st.secrets["google"].get("folder_id", "")
        except:
            pass
        
        if not root_folder_id:
            root_folder_id = os.getenv("GOOGLE_FOLDER_ID", "")
        
        if not root_folder_id:
            return {}
        
        # Get major-specific folder
        major_folder_id = gd.get_major_folder_id(service, major, root_folder_id)
        
        file_id = gd.find_file_in_drive(service, _filename(), major_folder_id)
        if not file_id:
            return {}
        payload = gd.download_file_from_drive(service, file_id)
        try:
            data = json.loads(payload.decode("utf-8"))
            # Normalize to {str(student_id): [codes...]}
            out: Dict[str, List[str]] = {}
            if isinstance(data, dict):
                for k, v in data.items():
                    key = str(k)
                    if isinstance(v, list):
                        out[key] = [str(c) for c in v]
            return out
        except Exception:
            return {}
    except Exception as e:
        log_error("Failed to load course exclusions from Drive", e)
        return {}


def _save_to_drive(ex_map: Dict[str, List[str]]) -> None:
    """
    Write exclusions map to Drive (overwrites the file).
    Best-effort: failures are logged but don't crash the UI.
    """
    import os
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        major = st.session_state.get("current_major", "DEFAULT")
        
        # Safe access to root folder_id
        root_folder_id = ""
        try:
            if "google" in st.secrets:
                root_folder_id = st.secrets["google"].get("folder_id", "")
        except:
            pass
        
        if not root_folder_id:
            root_folder_id = os.getenv("GOOGLE_FOLDER_ID", "")
        
        if not root_folder_id:
            log_info("Course exclusions saved locally only (no Drive folder configured).")
            return
        
        # Get major-specific folder
        major_folder_id = gd.get_major_folder_id(service, major, root_folder_id)
        
        data_bytes = json.dumps(ex_map, ensure_ascii=False, indent=2).encode("utf-8")
        gd.sync_file_with_drive(
            service=service,
            file_content=data_bytes,
            drive_file_name=_filename(),
            mime_type="application/json",
            parent_folder_id=major_folder_id,
        )
        log_info(f"Course exclusions saved to Drive: {major}/{_filename()}")
    except Exception as e:
        # Don't crash UI if Drive sync fails - data is saved locally
        log_error(f"Failed to sync course exclusions to Drive (local copy preserved): {str(e)}", e)
        st.warning(f"⚠️ Hidden courses saved locally but couldn't sync to Drive. They will persist in your current session.")


def ensure_loaded() -> None:
    """
    Ensure exclusions live in session (and per-major bucket if present).
    Called at the start of any page that needs exclusions.
    """
    major = st.session_state.get("current_major", "DEFAULT")
    # If majors bucket exists, keep per-major storage there
    if "majors" in st.session_state:
        bucket = st.session_state.majors.setdefault(major, {})
        if "course_exclusions" not in bucket:
            bucket["course_exclusions"] = _load_from_drive()
        st.session_state.course_exclusions = bucket["course_exclusions"]
    else:
        if "course_exclusions" not in st.session_state:
            st.session_state.course_exclusions = _load_from_drive()


def _persist_to_bucket():
    """Keep majors bucket in sync with session copy."""
    major = st.session_state.get("current_major", "DEFAULT")
    if "majors" in st.session_state:
        st.session_state.majors.setdefault(major, {})
        st.session_state.majors[major]["course_exclusions"] = st.session_state.get("course_exclusions", {})


def get_for_student(student_id: Union[int, str]) -> List[str]:
    """Return list of hidden course codes for a student (strings)."""
    ensure_loaded()
    sid = str(student_id)
    ex_map: Dict[str, List[str]] = st.session_state.get("course_exclusions", {})
    return list(ex_map.get(sid, []))


def set_for_student(student_id: Union[int, str], course_codes: List[str]) -> None:
    """
    Replace the hidden list for a student and sync to Drive.
    Accepts list of strings (course codes).
    """
    ensure_loaded()
    sid = str(student_id)
    ex_map: Dict[str, List[str]] = st.session_state.get("course_exclusions", {})
    ex_map[sid] = [str(c) for c in course_codes]
    st.session_state.course_exclusions = ex_map
    _persist_to_bucket()
    _save_to_drive(ex_map)
