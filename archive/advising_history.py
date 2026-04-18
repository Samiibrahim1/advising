# advising_history.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from uuid import uuid4
from datetime import datetime
import numpy as np

import pandas as pd
import streamlit as st

# Import eligibility functions from standalone module (no Streamlit dependencies)
from eligibility_utils import (
    check_course_completed,
    check_course_registered,
    is_course_offered,
    check_eligibility,
    build_requisites_str,
    get_student_standing,
    get_mutual_concurrent_pairs,
)

# Import logging from utils (lightweight, no circular deps)
from advising_utils import log_info, log_error, style_df

from advising_period import get_current_period

# Lazy import for Google Drive to prevent import-time initialization
_drive_module = None

def _get_drive_module():
    """Lazy load google_drive module to prevent import-time side effects."""
    global _drive_module
    if _drive_module is None:
        import google_drive as gd
        _drive_module = gd
    return _drive_module

try:
    from zoneinfo import ZoneInfo
    _LOCAL_TZ = ZoneInfo("Asia/Beirut")
except Exception:
    _LOCAL_TZ = None


# ---------- Local cache file paths ----------

def _get_local_cache_dir() -> str:
    """Get or create local cache directory for faster loading."""
    # Use a .cache folder in the current working directory
    cache_dir = os.path.join(os.getcwd(), ".advising_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def _get_local_index_path(major: str) -> str:
    """Get path to local index cache file for a major."""
    cache_dir = _get_local_cache_dir()
    return os.path.join(cache_dir, f"advising_index_{major}.json")

def _get_local_selections_path(major: str) -> str:
    """Get path to local selections cache file for a major."""
    cache_dir = _get_local_cache_dir()
    return os.path.join(cache_dir, f"advising_selections_{major}.json")

__all__ = [
    "advising_history_panel", 
    "autosave_current_student_session", 
    "save_session_for_student", 
    "_find_latest_session_for_student", 
    "_load_session_and_apply",
    "reload_student_session_from_drive",
    "load_all_sessions_for_period",
    "get_students_with_saved_sessions",
    "bulk_restore_sessions",
    "bulk_restore_panel",
    # Local cache helpers (for settings page)
    "_get_local_cache_dir",
    "_get_local_index_path",
    "_get_local_selections_path",
]


# ---------- internal helpers ----------

def _convert_to_json_serializable(obj: Any) -> Any:
    """Recursively convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj

def _now_beirut() -> datetime:
    return datetime.now(_LOCAL_TZ) if _LOCAL_TZ else datetime.now()

def _index_name() -> str:
    return "advising_index.json"

def _session_filename(session_id: str) -> str:
    return f"advising_session_{session_id}.json"


# ---------- index I/O ----------

def _get_major_folder_id() -> str:
    """Get major-specific folder ID. Returns major-specific folder inside root folder."""
    from advising_utils import get_major_folder_id_helper
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        return get_major_folder_id_helper(service)
    except Exception:
        return ""

def _get_sessions_folder_id() -> str:
    """Get sessions subfolder ID within the major folder. Creates it if it doesn't exist."""
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        major_folder_id = _get_major_folder_id()
        if not major_folder_id:
            return ""
        
        # Get or create 'sessions' subfolder within major folder
        sessions_folder_id = gd.get_or_create_folder(service, "sessions", major_folder_id)
        return sessions_folder_id
    except Exception as e:
        log_error(f"Failed to get/create sessions folder", e)
        return ""

def _load_index(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Load advising index with local-first approach for speed.
    Priority: 1) Session state cache, 2) Local file cache, 3) Google Drive
    Set force_refresh=True to force reload from Drive.
    """
    major = st.session_state.get("current_major", "DEFAULT")
    cache_key = f"_advising_index_cache_{major}"
    
    # 1. Use session state cache if available (fastest - in memory)
    if not force_refresh and cache_key in st.session_state:
        cached_index = st.session_state[cache_key]
        if cached_index:
            return cached_index
    
    # 2. Try local file cache (fast - disk read)
    if not force_refresh:
        local_path = _get_local_index_path(major)
        if os.path.exists(local_path):
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    local_index = json.load(f)
                if isinstance(local_index, list) and local_index:
                    _save_index_local(local_index)
                    log_info(f"Loaded index from local cache: {len(local_index)} entries")
                    return local_index
            except Exception as e:
                log_error("Failed to read local index cache", e)
    
    # 3. Fall back to Google Drive (slow - network)
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        
        # Try sessions subfolder first
        folder_id = _get_sessions_folder_id()
        if folder_id:
            fid = gd.find_file_in_drive(service, _index_name(), folder_id)
            if fid:
                payload = gd.download_file_from_drive(service, fid)
                idx = json.loads(payload.decode("utf-8"))
                result = idx if isinstance(idx, list) else []
                # Save to both session state AND local file
                _save_index_local(result)
                _save_index_to_local_file(result, major)
                return result
        
        # Fall back to major folder root (backward compatibility for legacy sessions)
        folder_id = _get_major_folder_id()
        if folder_id:
            fid = gd.find_file_in_drive(service, _index_name(), folder_id)
            if fid:
                payload = gd.download_file_from_drive(service, fid)
                idx = json.loads(payload.decode("utf-8"))
                log_info("Loaded legacy advising index from major folder root (consider migrating to sessions/)")
                result = idx if isinstance(idx, list) else []
                _save_index_local(result)
                _save_index_to_local_file(result, major)
                return result
        
        # No index found - initialize empty
        _save_index_local([])
        return []
    except Exception as e:
        log_error("Failed to load advising index", e)
        return st.session_state.get(cache_key, [])


def _save_index_to_local_file(index_items: List[Dict[str, Any]], major: str = None) -> None:
    """Save index to local file for fast loading on next visit."""
    if major is None:
        major = st.session_state.get("current_major", "DEFAULT")
    try:
        local_path = _get_local_index_path(major)
        serializable_items = _convert_to_json_serializable(index_items)
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error("Failed to save local index cache", e)

def _save_index_local(index_items: List[Dict[str, Any]]) -> None:
    """Save index to session state immediately (local-first)."""
    st.session_state.advising_index = index_items
    # Also update the cache
    major = st.session_state.get("current_major", "DEFAULT")
    cache_key = f"_advising_index_cache_{major}"
    st.session_state[cache_key] = index_items

def _save_index(index_items: List[Dict[str, Any]]) -> None:
    """Save index to local cache, session state, and Drive."""
    # Save locally first (instant)
    _save_index_local(index_items)
    _save_index_to_local_file(index_items)
    
    # Background save to Drive (best effort)
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        folder_id = _get_sessions_folder_id()
        if not folder_id:
            return
        # Convert numpy types to native Python types before JSON serialization
        serializable_items = _convert_to_json_serializable(index_items)
        data = json.dumps(serializable_items, ensure_ascii=False, indent=2).encode("utf-8")
        gd.sync_file_with_drive(service, data, _index_name(), "application/json", folder_id)
        log_info(f"Index saved to Drive/sessions: {_index_name()}")
    except Exception as e:
        log_error("Failed to save advising index to Drive (local copy preserved)", e)


# ---------- session payload I/O ----------

def _save_session_payload_local(session_id: str, snapshot: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """Save session payload to session state immediately (local-first)."""
    if "advising_sessions_cache" not in st.session_state:
        st.session_state.advising_sessions_cache = {}
    st.session_state.advising_sessions_cache[session_id] = {"meta": meta, "snapshot": snapshot}

def _save_session_payload(session_id: str, snapshot: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """Save session payload with local-first approach."""
    # Save locally first (instant)
    _save_session_payload_local(session_id, snapshot, meta)
    
    # Background save to Drive (best effort, non-blocking)
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        folder_id = _get_sessions_folder_id()
        if not folder_id:
            log_info(f"Session saved locally only (no Drive folder configured): {session_id}")
            return
        # Convert numpy types to native Python types before JSON serialization
        payload = _convert_to_json_serializable({"meta": meta, "snapshot": snapshot})
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        gd.sync_file_with_drive(service, data, _session_filename(session_id), "application/json", folder_id)
        log_info(f"Session payload synced to Drive/sessions: {_session_filename(session_id)}")
    except Exception as e:
        log_error(f"Failed to sync session to Drive (local copy preserved): {session_id}", e)

def _delete_session_from_drive(session_id: str) -> bool:
    """Delete a session file from Drive. Returns True if successful."""
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        
        # Try sessions subfolder first
        folder_id = _get_sessions_folder_id()
        if folder_id:
            fid = gd.find_file_in_drive(service, _session_filename(session_id), folder_id)
            if fid:
                gd.delete_file_from_drive(service, fid)
                log_info(f"Deleted session from Drive: {session_id}")
                return True
        
        # Try major folder root (backward compatibility)
        folder_id = _get_major_folder_id()
        if folder_id:
            fid = gd.find_file_in_drive(service, _session_filename(session_id), folder_id)
            if fid:
                gd.delete_file_from_drive(service, fid)
                log_info(f"Deleted legacy session from Drive: {session_id}")
                return True
        
        return False
    except Exception as e:
        log_error(f"Failed to delete session from Drive: {session_id}", e)
        return False


def _delete_sessions(session_ids: List[str]) -> int:
    """Delete multiple sessions from both index and Drive. Returns count deleted."""
    if not session_ids:
        return 0
    
    deleted_count = 0
    
    # Remove from index
    if "advising_index" not in st.session_state:
        st.session_state.advising_index = _load_index()
    
    original_count = len(st.session_state.advising_index)
    st.session_state.advising_index = [
        r for r in st.session_state.advising_index 
        if str(r.get("id", "")) not in session_ids
    ]
    deleted_count = original_count - len(st.session_state.advising_index)
    
    # Save updated index
    _save_index(st.session_state.advising_index)
    
    # Remove from local cache
    if "advising_sessions_cache" in st.session_state:
        for sid in session_ids:
            st.session_state.advising_sessions_cache.pop(sid, None)
    
    # Delete from Drive (best effort)
    for sid in session_ids:
        _delete_session_from_drive(sid)
    
    return deleted_count


def _load_session_payload_by_id(session_id: str) -> Optional[Dict[str, Any]]:
    # Try local cache first
    if "advising_sessions_cache" in st.session_state:
        cached = st.session_state.advising_sessions_cache.get(session_id)
        if cached:
            return cached
    
    # Fall back to Drive
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        
        # Try sessions subfolder first
        folder_id = _get_sessions_folder_id()
        if folder_id:
            fid = gd.find_file_in_drive(service, _session_filename(session_id), folder_id)
            if fid:
                data = gd.download_file_from_drive(service, fid)
                payload = json.loads(data.decode("utf-8"))
                # Cache it locally for next time
                _save_session_payload_local(session_id, payload.get("snapshot", {}), payload.get("meta", {}))
                return payload
        
        # Fall back to major folder root (backward compatibility for legacy sessions)
        folder_id = _get_major_folder_id()
        if folder_id:
            fid = gd.find_file_in_drive(service, _session_filename(session_id), folder_id)
            if fid:
                data = gd.download_file_from_drive(service, fid)
                payload = json.loads(data.decode("utf-8"))
                log_info(f"Loaded legacy session {session_id} from major folder root")
                # Cache it locally for next time
                _save_session_payload_local(session_id, payload.get("snapshot", {}), payload.get("meta", {}))
                return payload
        
        return None
    except Exception as e:
        log_error("Failed to load session payload from Drive", e)
        return None


# ---------- snapshot builders ----------

def _snapshot_courses_table() -> List[Dict[str, Any]]:
    df = st.session_state.get("courses_df", pd.DataFrame())
    if df.empty:
        return []
    cols = [
        "Course Code", "Type", "Credits", "Offered",
        "Prerequisite", "Concurrent", "Corequisite",
        "Title", "Requisites",
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].fillna("").to_dict(orient="records")

def _find_student_row(student_id: Union[int, str]) -> Optional[pd.Series]:
    pdf = st.session_state.get("progress_df", pd.DataFrame())
    if pdf.empty:
        return None
    row = pdf.loc[pdf["ID"] == student_id]
    if not row.empty:
        return row.iloc[0]
    try:
        row = pdf.loc[pdf["ID"] == int(student_id)]
        if not row.empty:
            return row.iloc[0]
    except Exception:
        pass
    try:
        row = pdf.loc[pdf["ID"].astype(str) == str(student_id)]
        if not row.empty:
            return row.iloc[0]
    except Exception:
        pass
    return None

def _snapshot_student_courses(student_row: pd.Series, advised: List[str], optional: List[str], repeat: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    cdf = st.session_state.courses_df
    mutual_pairs = get_mutual_concurrent_pairs(cdf)
    for _, info in cdf.iterrows():
        code = str(info["Course Code"])
        offered = "Yes" if is_course_offered(cdf, code) else "No"
        status, justification = check_eligibility(student_row, code, advised, cdf, registered_courses=[], mutual_pairs=mutual_pairs)

        # Action column should ONLY show advisor selections
        if code in repeat:
            action = "Advised-Repeat"
        elif code in advised:
            action = "Advised"
        elif code in optional:
            action = "Optional"
        else:
            action = ""  # Empty for non-selected courses
        
        # Update status for completed/registered courses (for Eligibility Status column)
        if check_course_completed(student_row, code):
            status = "Completed"
        elif check_course_registered(student_row, code):
            status = "Registered"

        rows.append({
            "Course Code": code,
            "Type": info.get("Type", ""),
            "Title": info.get("Title", ""),
            "Requisites": build_requisites_str(info),
            "Offered": offered,
            "Eligibility Status": status,
            "Justification": justification,
            "Action": action,
        })
    return rows

def _build_single_student_snapshot(student_id: Union[int, str]) -> Dict[str, Any]:
    srow = _find_student_row(student_id)
    if srow is None:
        return {"courses_table": _snapshot_courses_table(), "students": []}

    selections = st.session_state.get("advising_selections", {}) or {}
    sel = (
        selections.get(student_id)
        or selections.get(str(student_id))
        or (selections.get(int(student_id)) if str(student_id).isdigit() else None)
        or {}
    )

    advised = [str(x) for x in sel.get("advised", [])]
    optional = [str(x) for x in sel.get("optional", [])]
    repeat = [str(x) for x in sel.get("repeat", [])]
    note = str(sel.get("note", "") or "")
    
    # Get bypasses for this student
    major = st.session_state.get("current_major", "")
    bypasses_key = f"bypasses_{major}"
    all_bypasses = st.session_state.get(bypasses_key, {})
    student_bypasses = (
        all_bypasses.get(student_id)
        or all_bypasses.get(str(student_id))
        or (all_bypasses.get(int(student_id)) if str(student_id).isdigit() else None)
        or {}
    )

    credits_completed = float(srow.get("# of Credits Completed", 0) or 0)
    credits_registered = float(srow.get("# Registered", 0) or 0)
    standing = get_student_standing(credits_completed + credits_registered)

    return {
        "courses_table": _snapshot_courses_table(),
        "students": [{
            "ID": srow["ID"],
            "NAME": str(srow.get("NAME")),
            "# of Credits Completed": credits_completed,
            "# Registered": credits_registered,
            "Standing": standing,
            "advised": advised,
            "optional": optional,
            "repeat": repeat,
            "note": note,
            "bypasses": student_bypasses,
            "courses": _snapshot_student_courses(srow, advised, optional, repeat),
        }],
    }


# ---------- public save APIs ----------

def save_session_for_student(student_id: Union[int, str]) -> Optional[str]:
    """
    Build a snapshot for *this* student and persist it.
    Does NOT depend on st.session_state['current_student_id'].
    """
    try:
        snapshot = _build_single_student_snapshot(student_id)
        students = snapshot.get("students", [])
        if not students:
            log_error("save_session_for_student: no student row", Exception("student_not_found"))
            return None

        student_name = str(students[0].get("NAME", ""))
        now = _now_beirut()
        sid = str(uuid4())
        
        # Get current period information
        current_period = get_current_period()
        year = current_period.get("year", "")
        
        # Format academic year (e.g., 2024 -> 2024/2025)
        try:
            year_int = int(year)
            academic_year = f"{year_int}/{year_int + 1}"
        except (ValueError, TypeError):
            academic_year = year
        
        # Session title includes date, student, and academic year
        title = f"{now.strftime('%Y-%m-%d %H:%M')} — {student_name} ({student_id}) | {academic_year}"
        
        meta = {
            "id": sid,
            "title": title,
            "created_at": now.isoformat(),
            "major": st.session_state.get("current_major", ""),
            "student_id": students[0].get("ID", student_id),
            "student_name": student_name,
            "period_id": current_period.get("period_id", ""),
            "semester": current_period.get("semester", ""),
            "year": current_period.get("year", ""),
            "advisor_name": current_period.get("advisor_name", ""),
        }

        # best-effort payload save to Drive
        _save_session_payload(sid, snapshot, meta)

        # FIX RACE CONDITION: Force reload index from Drive before appending
        # This ensures we have the latest entries from other users
        st.session_state.advising_index = _load_index(force_refresh=True)
        
        student_data = students[0]
        st.session_state.advising_index.append({
            "id": sid,
            "title": title,
            "created_at": meta["created_at"],
            "student_id": meta["student_id"],
            "student_name": meta["student_name"],
            "major": meta["major"],
            "session_file": _session_filename(sid),
            "period_id": meta["period_id"],
            "semester": meta["semester"],
            "year": meta["year"],
            "advisor_name": meta["advisor_name"],
            # Summary data for instant loading
            "advised": student_data.get("advised", []),
            "optional": student_data.get("optional", []),
            "repeat": student_data.get("repeat", []),
        })
        _save_index(st.session_state.advising_index)
        
        # Also update local selections cache
        major = st.session_state.get("current_major", "")
        _save_selections_to_local_file(major)

        log_info(f"Auto-saved advising session for {student_id}: {title}")
        return sid
    except Exception as e:
        log_error("save_session_for_student failed", e)
        return None


def autosave_current_student_session() -> Optional[str]:
    """Legacy hook—kept for compatibility. Uses explicit saver if possible."""
    sid = st.session_state.get("current_student_id", None)
    if sid is None:
        log_error("autosave_current_student_session: no current_student_id", Exception("no_current_student"))
        return None
    return save_session_for_student(sid)


def _find_latest_session_for_student(student_id: Union[int, str], period_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Find the most recent advising session for a given student.
    If period_id is provided, only returns sessions from that period.
    If period_id is None, uses current period.
    Returns the session metadata if found, None otherwise.
    """
    if "advising_index" not in st.session_state:
        st.session_state.advising_index = _load_index()
    
    index = st.session_state.advising_index or []
    
    # Get period filter
    if period_id is None:
        current_period = get_current_period()
        period_id = current_period.get("period_id", "")
    
    # Filter sessions strictly to this student AND this period only.
    # Do NOT fall back to other periods — that causes old selections to bleed
    # into a new advising period.
    student_sessions = [
        r for r in index
        if str(r.get("student_id", "")) == str(student_id)
        and r.get("period_id", "") == period_id
    ]

    if not student_sessions:
        return None
    
    # Sort by created_at (most recent first)
    student_sessions.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    
    return student_sessions[0]


def _load_session_and_apply(student_id: Union[int, str]) -> bool:
    """
    Load the most recent advising session for a student and apply it to the current state.
    Returns True if a session was loaded, False otherwise.
    """
    latest_session = _find_latest_session_for_student(student_id)
    
    if not latest_session:
        return False
    
    session_id = latest_session.get("id")
    if not session_id:
        return False
    
    # Load the session payload
    payload = _load_session_payload_by_id(session_id)
    if not payload:
        return False
    
    snapshot = payload.get("snapshot", {})
    students = snapshot.get("students", [])
    
    if not students:
        return False
    
    student_data = students[0]
    
    # Apply to advising_selections
    if "advising_selections" not in st.session_state:
        st.session_state.advising_selections = {}
    
    st.session_state.advising_selections[student_id] = {
        "advised": student_data.get("advised", []),
        "optional": student_data.get("optional", []),
        "repeat": student_data.get("repeat", []),
        "note": student_data.get("note", ""),
    }
    
    # Apply bypasses (backward compatible - old sessions won't have this field)
    student_bypasses = student_data.get("bypasses", {})
    if student_bypasses:
        major = st.session_state.get("current_major", "")
        bypasses_key = f"bypasses_{major}"
        if bypasses_key not in st.session_state:
            st.session_state[bypasses_key] = {}
        st.session_state[bypasses_key][student_id] = student_bypasses
    
    log_info(f"Auto-loaded most recent session for student {student_id}")
    return True


def reload_student_session_from_drive(student_id: Union[int, str]) -> bool:
    """
    Force reload a specific student's most recent session from Drive.
    Useful when switching students to ensure we have the latest data.
    
    Returns True if successfully loaded, False otherwise.
    """
    # Remove from cache so it gets reloaded
    sid_int = int(student_id) if str(student_id).isdigit() else student_id
    sid_str = str(student_id)
    
    # Remove from advising_selections to allow reload
    if "advising_selections" in st.session_state:
        st.session_state.advising_selections.pop(sid_int, None)
        st.session_state.advising_selections.pop(sid_str, None)
    
    # Remove the autoload flag to allow re-loading
    st.session_state.pop(f"_autoloaded_{sid_int}", None)
    st.session_state.pop(f"_autoloaded_{sid_str}", None)
    
    # Now load the session
    return _load_session_and_apply(student_id)


def _save_selections_to_local_file(major: str = None) -> None:
    """Save current advising_selections to local file for fast loading."""
    if major is None:
        major = st.session_state.get("current_major", "DEFAULT")
    try:
        selections = st.session_state.get("advising_selections", {})
        bypasses_key = f"bypasses_{major}"
        bypasses = st.session_state.get(bypasses_key, {})
        
        # Convert keys to strings for JSON compatibility
        serializable_selections = {str(k): _convert_to_json_serializable(v) for k, v in selections.items()}
        serializable_bypasses = {str(k): _convert_to_json_serializable(v) for k, v in bypasses.items()}
        
        data = {
            "selections": serializable_selections,
            "bypasses": serializable_bypasses,
            "saved_at": _now_beirut().isoformat() if _LOCAL_TZ else datetime.now().isoformat(),
        }
        
        local_path = _get_local_selections_path(major)
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error("Failed to save local selections cache", e)


def _load_selections_from_local_file(major: str = None) -> bool:
    """Load advising_selections from local file. Returns True if loaded successfully with data."""
    if major is None:
        major = st.session_state.get("current_major", "DEFAULT")
    try:
        local_path = _get_local_selections_path(major)
        if not os.path.exists(local_path):
            return False
        
        with open(local_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        selections = data.get("selections", {})
        bypasses = data.get("bypasses", {})
        
        # Only return True if we actually have selections data
        if not selections:
            log_info("Local selections cache exists but is empty - will load from Drive")
            return False
        
        # Convert string keys back to int where possible
        if "advising_selections" not in st.session_state:
            st.session_state.advising_selections = {}
        
        for k, v in selections.items():
            try:
                norm_k = int(k)
            except (ValueError, TypeError):
                norm_k = k
            st.session_state.advising_selections[norm_k] = v
        
        bypasses_key = f"bypasses_{major}"
        if bypasses_key not in st.session_state:
            st.session_state[bypasses_key] = {}
        
        for k, v in bypasses.items():
            try:
                norm_k = int(k)
            except (ValueError, TypeError):
                norm_k = k
            st.session_state[bypasses_key][norm_k] = v
        
        log_info(f"Loaded {len(selections)} selections from local cache")
        return True
    except Exception as e:
        log_error("Failed to load local selections cache", e)
        return False


def load_all_sessions_for_period(period_id: Optional[str] = None, force_refresh: bool = False) -> int:
    """
    Load all saved advising sessions for the current (or specified) period
    and apply them to advising_selections.
    
    Uses local-first approach:
    1. Try local file cache (instant)
    2. Try session state (in-memory)  
    3. Fall back to Drive index (network)
    
    Args:
        period_id: The period to load. If None, uses current period.
        force_refresh: If True, force reload from Drive and refresh ALL caches.
    
    Returns the number of sessions loaded.
    """
    major = st.session_state.get("current_major", "")
    
    # Try local file cache first (fastest - no network)
    # Only use local cache if NOT force_refresh AND it has actual data
    if not force_refresh:
        local_loaded = _load_selections_from_local_file(major)
        if local_loaded:
            selections_count = len(st.session_state.get("advising_selections", {}))
            if selections_count > 0:
                log_info(f"Using local cache: {selections_count} selections")
                return selections_count
            # If local cache returned True but no selections, continue to Drive
    
    # Load index (uses local-first approach internally)
    if "advising_index" not in st.session_state or force_refresh:
        st.session_state.advising_index = _load_index(force_refresh=force_refresh)
    
    index = st.session_state.advising_index or []
    
    if period_id is None:
        current_period = get_current_period()
        period_id = current_period.get("period_id", "")
    
    period_sessions = [
        r for r in index 
        if r.get("period_id", "") == period_id
    ]
    
    if not period_sessions:
        return 0
    
    students_with_sessions = {}
    for session in period_sessions:
        student_id = session.get("student_id")
        if not student_id:
            continue
        created_at = session.get("created_at", "")
        if student_id not in students_with_sessions or created_at > students_with_sessions[student_id].get("created_at", ""):
            students_with_sessions[student_id] = session
    
    if "advising_selections" not in st.session_state:
        st.session_state.advising_selections = {}
    
    major = st.session_state.get("current_major", "")
    bypasses_key = f"bypasses_{major}"
    if bypasses_key not in st.session_state:
        st.session_state[bypasses_key] = {}
    
    loaded_count = 0
    for student_id, session_meta in students_with_sessions.items():
        try:
            norm_id = int(student_id)
        except (ValueError, TypeError):
            norm_id = str(student_id)
        
        # Only skip if not force_refresh AND data already loaded
        if not force_refresh and (norm_id in st.session_state.advising_selections or str(norm_id) in st.session_state.advising_selections):
            continue
        
        session_id = session_meta.get("id")
        if not session_id:
            continue
        
        # USE INDEX SUMMARY DATA IF AVAILABLE (FAST!)
        if "advised" in session_meta:
             st.session_state.advising_selections[norm_id] = {
                "advised": session_meta.get("advised", []),
                "optional": session_meta.get("optional", []),
                "repeat": session_meta.get("repeat", []),
                "note": session_meta.get("note", ""), # may still be missing in index
            }
             loaded_count += 1
             continue
             
        # FALLBACK: Load from Drive for legacy entries (SLOW)
        payload = _load_session_payload_by_id(session_id)
        if not payload:
            continue
        
        snapshot = payload.get("snapshot", {})
        students = snapshot.get("students", [])
        
        if not students:
            continue
        
        student_data = students[0]
        
        st.session_state.advising_selections[norm_id] = {
            "advised": student_data.get("advised", []),
            "optional": student_data.get("optional", []),
            "repeat": student_data.get("repeat", []),
            "note": student_data.get("note", ""),
        }
        
        student_bypasses = student_data.get("bypasses", {})
        if student_bypasses:
            st.session_state[bypasses_key][norm_id] = student_bypasses
        
        loaded_count += 1
    
    if loaded_count > 0:
        log_info(f"Loaded {loaded_count} advising sessions for period {period_id}")
        # Save to local cache for faster loading next time
        _save_selections_to_local_file(major)
    
    return loaded_count


# ---------- bulk restore helpers ----------

def get_students_with_saved_sessions(period_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get list of students who have saved sessions in the current period.
    Returns list of dicts with student_id, student_name, session_count, latest_session info.
    """
    index = _load_index()
    if not index:
        return []
    
    if period_id is None:
        current_period = get_current_period()
        period_id = current_period.get("period_id", "")
    
    # Filter sessions for current period
    period_sessions = [r for r in index if str(r.get("period_id", "")) == str(period_id)]
    
    # Group by student
    students_info: Dict[str, Dict[str, Any]] = {}
    for session in period_sessions:
        student_id = session.get("student_id")
        if not student_id:
            continue
        
        sid_str = str(student_id)
        if sid_str not in students_info:
            students_info[sid_str] = {
                "student_id": student_id,
                "student_name": session.get("student_name", ""),
                "session_count": 0,
                "latest_session_id": None,
                "latest_created_at": "",
                "created_at": "", # for sort
            }
        
        info = students_info[sid_str]
        info["session_count"] += 1
        
        created_at = session.get("created_at", "")
        if not info["latest_created_at"] or created_at > info["latest_created_at"]:
            info["latest_created_at"] = created_at
            info["created_at"] = created_at
            info["latest_session_id"] = session.get("id")
            
    return sorted(list(students_info.values()), key=lambda x: x["latest_created_at"], reverse=True)

def get_advised_student_ids(period_id: Optional[str] = None, force_refresh: bool = False) -> Set[Union[int, str]]:
    """
    Get a set of all student IDs who have at least one session in the specified period.
    This is FAST as it only uses the index.
    """
    index = _load_index(force_refresh=force_refresh)
    if not index:
        return set()
    
    if period_id is None:
        from advising_period import get_current_period
        current_period = get_current_period()
        period_id = current_period.get("period_id", "")
    
    return {
        entry.get("student_id") 
        for entry in index 
        if str(entry.get("period_id", "")) == str(period_id) and entry.get("student_id")
    }


def bulk_restore_sessions(student_ids: List[Union[int, str]], force: bool = False) -> Dict[str, Any]:
    """
    Restore most recent saved sessions for multiple students at once.
    
    Args:
        student_ids: List of student IDs to restore
        force: If True, overwrite existing advising_selections. If False, skip already loaded.
    
    Returns:
        Dict with 'restored', 'skipped', 'failed' counts and 'details' list
    """
    result = {
        "restored": 0,
        "skipped": 0,
        "failed": 0,
        "details": []
    }
    
    if "advising_selections" not in st.session_state:
        st.session_state.advising_selections = {}
    
    major = st.session_state.get("current_major", "")
    bypasses_key = f"bypasses_{major}"
    if bypasses_key not in st.session_state:
        st.session_state[bypasses_key] = {}
    
    for student_id in student_ids:
        try:
            # Normalize ID
            try:
                norm_id = int(student_id)
            except (ValueError, TypeError):
                norm_id = str(student_id)
            
            # Check if already loaded (unless force=True)
            if not force:
                if norm_id in st.session_state.advising_selections:
                    existing = st.session_state.advising_selections[norm_id]
                    if existing.get("advised") or existing.get("optional") or existing.get("note"):
                        result["skipped"] += 1
                        result["details"].append({
                            "student_id": student_id,
                            "status": "skipped",
                            "reason": "Already has active session"
                        })
                        continue
            
            # Find and load latest session
            latest_session = _find_latest_session_for_student(student_id)
            if not latest_session:
                result["failed"] += 1
                result["details"].append({
                    "student_id": student_id,
                    "status": "failed",
                    "reason": "No saved session found"
                })
                continue
            
            session_id = latest_session.get("id")
            payload = _load_session_payload_by_id(session_id)
            if not payload:
                result["failed"] += 1
                result["details"].append({
                    "student_id": student_id,
                    "status": "failed",
                    "reason": "Could not load session payload"
                })
                continue
            
            snapshot = payload.get("snapshot", {})
            students = snapshot.get("students", [])
            if not students:
                result["failed"] += 1
                result["details"].append({
                    "student_id": student_id,
                    "status": "failed",
                    "reason": "Session has no student data"
                })
                continue
            
            student_data = students[0]
            
            # Apply to advising_selections
            st.session_state.advising_selections[norm_id] = {
                "advised": student_data.get("advised", []),
                "optional": student_data.get("optional", []),
                "repeat": student_data.get("repeat", []),
                "note": student_data.get("note", ""),
            }
            
            # Apply bypasses
            student_bypasses = student_data.get("bypasses", {})
            if student_bypasses:
                st.session_state[bypasses_key][norm_id] = student_bypasses
            
            result["restored"] += 1
            result["details"].append({
                "student_id": student_id,
                "student_name": latest_session.get("student_name", ""),
                "status": "restored",
                "session_date": latest_session.get("created_at", "")[:16]
            })
            
        except Exception as e:
            result["failed"] += 1
            result["details"].append({
                "student_id": student_id,
                "status": "failed",
                "reason": str(e)
            })
    
    if result["restored"] > 0:
        log_info(f"Bulk restored {result['restored']} sessions")
        # Invalidate caches that depend on advising data
        if "_conflict_insights_cache" in st.session_state:
            del st.session_state["_conflict_insights_cache"]
        
        # Sync to per-major bucket so it persists across reruns
        major = st.session_state.get("current_major", "")
        if major and "majors" in st.session_state:
            if major in st.session_state.majors:
                st.session_state.majors[major]["advising_selections"] = st.session_state.advising_selections.copy()
    
    return result


def bulk_restore_panel():
    """
    UI panel for bulk restoring saved sessions.
    Shows students with saved sessions and allows selecting multiple to restore.
    """
    st.markdown("---")
    st.subheader("Restore Saved Sessions")
    st.caption("Restore advising sessions from saved archive to make them active and editable.")
    
    # Get students with saved sessions
    students_with_sessions = get_students_with_saved_sessions()
    
    if not students_with_sessions:
        st.info("No saved sessions found for the current advising period.")
        return
    
    # Get current advising_selections to identify what's already loaded
    current_selections = st.session_state.get("advising_selections", {})
    
    # Build display data
    display_data = []
    for s in students_with_sessions:
        sid = s["student_id"]
        
        # Check if already has active session
        sel = current_selections.get(sid) or current_selections.get(str(sid)) or {}
        has_active = bool(sel.get("advised") or sel.get("optional") or sel.get("note"))
        
        display_data.append({
            "student_id": sid,
            "student_name": s["student_name"],
            "session_count": s["session_count"],
            "latest_date": s["latest_created_at"][:16].replace("T", " ") if s["latest_created_at"] else "",
            "has_active": has_active,
            "status": "Active" if has_active else "Not Loaded"
        })
    
    # Sort by status (not loaded first), then name
    display_data.sort(key=lambda x: (x["has_active"], x["student_name"]))
    
    # Summary stats
    not_loaded_count = sum(1 for d in display_data if not d["has_active"])
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total with Saved Sessions", len(display_data))
    with c2:
        st.metric("Not Loaded", not_loaded_count)
    with c3:
        st.metric("Already Active", len(display_data) - not_loaded_count)
    
    # Create dataframe for selection
    df = pd.DataFrame(display_data)
    df = df.rename(columns={
        "student_id": "ID",
        "student_name": "Name", 
        "session_count": "Saved Sessions",
        "latest_date": "Latest Save",
        "status": "Status"
    })
    
    # Multi-select using checkboxes
    st.markdown("**Select students to restore:**")
    
    # Quick actions
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Select All Not Loaded", key="bulk_select_all"):
            st.session_state["_bulk_restore_selection"] = [
                str(d["student_id"]) for d in display_data if not d["has_active"]
            ]
            st.rerun()
    with col2:
        if st.button("Clear Selection", key="bulk_clear_selection"):
            st.session_state["_bulk_restore_selection"] = []
            st.rerun()
    
    # Initialize selection state
    if "_bulk_restore_selection" not in st.session_state:
        st.session_state["_bulk_restore_selection"] = []
    
    # Display as a data editor with selection column
    df_display = df[["ID", "Name", "Saved Sessions", "Latest Save", "Status"]].copy()
    df_display.insert(0, "Select", [str(d["student_id"]) in st.session_state["_bulk_restore_selection"] for d in display_data])
    
    edited_df = st.data_editor(
        df_display,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", default=False),
            "ID": st.column_config.NumberColumn("ID", format="%d"),
        },
        disabled=["ID", "Name", "Saved Sessions", "Latest Save", "Status"],
        hide_index=True,
        width=1200,
        key="bulk_restore_editor",
    )
    
    # Update selection from editor
    selected_ids = []
    for i, row in edited_df.iterrows():
        if row["Select"]:
            selected_ids.append(str(display_data[i]["student_id"]))
    
    st.session_state["_bulk_restore_selection"] = selected_ids
    
    # Restore options
    st.markdown(f"**{len(selected_ids)} student(s) selected**")
    
    force_overwrite = st.checkbox(
        "Force overwrite existing active sessions", 
        value=False,
        help="If checked, will overwrite any existing advising data. Otherwise, skips students who already have active sessions."
    )
    
    # Restore button
    if st.button("Restore Selected Sessions", type="primary", disabled=len(selected_ids) == 0, key="bulk_restore_btn"):
        with st.spinner(f"Restoring {len(selected_ids)} sessions..."):
            result = bulk_restore_sessions(selected_ids, force=force_overwrite)
        
        # Show results
        if result["restored"] > 0:
            st.success(f"Successfully restored {result['restored']} session(s)")
        if result["skipped"] > 0:
            st.info(f"Skipped {result['skipped']} session(s) (already have active data)")
        if result["failed"] > 0:
            st.warning(f"Failed to restore {result['failed']} session(s)")
        
        # Show details in expander
        if result["details"]:
            with st.expander("View Details"):
                details_df = pd.DataFrame(result["details"])
                st.dataframe(details_df, hide_index=True, width=1200)
        
        # Clear selection and refresh
        st.session_state["_bulk_restore_selection"] = []
        st.rerun()


# ---------- panel UI ----------

def advising_history_panel():
    st.markdown("---")
    st.subheader(f"Advising Sessions — {st.session_state.get('current_major','')}")
    if "advising_index" not in st.session_state:
        st.session_state.advising_index = _load_index()
    index = list(st.session_state.advising_index or [])

    current_sid = st.session_state.get("current_student_id", None)
    if current_sid is not None:
        index = [r for r in index if str(r.get("student_id","")) == str(current_sid)]

    c1, c2 = st.columns([2,1])
    with c1:
        q = st.text_input("Search", key="sess_search", placeholder="Title / student name / ID")
    with c2:
        sort_key = st.selectbox("Sort", ["Date desc", "Date asc", "Title"], index=0, key="sess_sort")

    if q:
        ql = q.lower()
        def _hit(r: Dict[str, Any]) -> bool:
            return (
                ql in str(r.get("title","")).lower()
                or ql in str(r.get("student_name","")).lower()
                or ql in str(r.get("student_id","")).lower()
            )
        index = [r for r in index if _hit(r)]

    if sort_key == "Date asc":
        index.sort(key=lambda r: r.get("created_at",""))
    elif sort_key == "Title":
        index.sort(key=lambda r: r.get("title",""))
    else:
        index.sort(key=lambda r: r.get("created_at",""), reverse=True)

    if not index:
        st.info("No sessions found for this student." if current_sid is not None else "No sessions found.")
        return

    # Session selector - deletion is managed via Google Drive for admin control
    labels = [r.get("title", "(untitled)") for r in index]
    choice_idx = st.selectbox(
        "Saved sessions", 
        options=list(range(len(index))), 
        format_func=lambda i: labels[i], 
        key="sess_choice"
    )
    chosen = index[choice_idx]
    sid = str(chosen.get("id", ""))
    
    if st.button("📂 View Session", use_container_width=True, key="sess_open"):
        payload = _load_session_payload_by_id(sid)
        if payload:
            st.session_state["advising_loaded_payload"] = payload
            st.success("Loaded archived session below (read-only).")
    
    st.caption("To delete sessions, manage files directly in Google Drive.")

    payload = st.session_state.get("advising_loaded_payload")
    if payload:
        snapshot = payload.get("snapshot", {})
        students = snapshot.get("students", [])
        if students:
            s = students[0]
            st.markdown("### Archived Session (read-only)")
            with st.container(border=True):
                st.write(
                    f"**Name:** {s.get('NAME','')}  |  **ID:** {s.get('ID','')}  |  "
                    f"**Credits:** {int((s.get('# of Credits Completed',0) or 0) + (s.get('# Registered',0) or 0))}  |  "
                    f"**Standing:** {s.get('Standing','')}"
                )
                if s.get("note"):
                    st.caption("Advisor Note:")
                    st.write(s["note"])
            df = pd.DataFrame(s.get("courses", []))
            if not df.empty:
                preferred = ["Course Code","Type","Requisites","Offered","Eligibility Status","Justification","Action"]
                cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
                st.dataframe(style_df(df[cols]), width=1200)
            else:
                st.info("No course rows stored in this snapshot.")
