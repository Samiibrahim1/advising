# advising_period.py
from __future__ import annotations

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import streamlit as st

from advising_utils import log_info, log_error

def _get_drive_module():
    """Lazy loader for google_drive module to avoid import-time side effects."""
    import google_drive as gd
    return gd

__all__ = [
    "get_current_period",
    "start_new_period",
    "get_all_periods",
    "load_period_from_drive",
    "save_period_to_drive",
]


PERIOD_FILENAME = "current_period.json"
PERIODS_HISTORY_FILENAME = "periods_history.json"


def _reconstruct_periods_from_sessions() -> List[Dict[str, Any]]:
    """
    Scan the advising index for period metadata and reconstruct period entries
    for any periods that have sessions but are missing from the history.
    This recovers periods that were lost due to sync issues.
    """
    try:
        # Lazy import to avoid circular dependency
        from advising_history import _load_index
        
        index = _load_index()
        if not index:
            return []
        
        # Extract unique periods from session metadata
        periods_from_sessions: Dict[str, Dict[str, Any]] = {}
        
        for session in index:
            period_id = session.get("period_id")
            if not period_id:
                continue
            
            # Only process if we haven't seen this period yet, or update with more info
            if period_id not in periods_from_sessions:
                periods_from_sessions[period_id] = {
                    "period_id": period_id,
                    "semester": session.get("semester", ""),
                    "year": session.get("year", ""),
                    "advisor_name": session.get("advisor_name", ""),
                    "created_at": session.get("created_at", ""),
                    "reconstructed": True,  # Mark as reconstructed
                }
            else:
                # Update with earlier created_at if available
                existing = periods_from_sessions[period_id]
                session_created = session.get("created_at", "")
                if session_created and (not existing.get("created_at") or session_created < existing["created_at"]):
                    existing["created_at"] = session_created
                # Fill in missing fields
                if not existing.get("advisor_name") and session.get("advisor_name"):
                    existing["advisor_name"] = session.get("advisor_name")
                if not existing.get("semester") and session.get("semester"):
                    existing["semester"] = session.get("semester")
                if not existing.get("year") and session.get("year"):
                    existing["year"] = session.get("year")
        
        return list(periods_from_sessions.values())
    except Exception as e:
        log_error("Failed to reconstruct periods from sessions", e)
        return []


def _get_major_folder_id_internal() -> str:
    """Get major-specific folder ID."""
    from advising_utils import get_major_folder_id_helper
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        return get_major_folder_id_helper(service)
    except Exception:
        return ""


def get_current_period() -> Dict[str, Any]:
    """
    Get current advising period for the selected major.
    Returns dict with semester, year, advisor_name, and period_id.
    Creates default if none exists.
    """
    major = st.session_state.get("current_major", "DEFAULT")
    
    # Check session state cache first
    if "current_periods" not in st.session_state:
        st.session_state.current_periods = {}
    
    if major in st.session_state.current_periods:
        return st.session_state.current_periods[major]
    
    # Try to load from Drive
    period = load_period_from_drive()
    
    # If no period found, create default
    if not period:
        current_year = datetime.now().year
        period = {
            "period_id": f"default_{current_year}",
            "semester": "Fall",
            "year": current_year,
            "advisor_name": "",
            "created_at": datetime.now().isoformat(),
        }
    
    st.session_state.current_periods[major] = period
    return period


def load_period_from_drive() -> Optional[Dict[str, Any]]:
    """Load current period from Drive for current major."""
    try:
        major = st.session_state.get("current_major", "DEFAULT")
        log_info(f"Attempting to load period from Drive for major {major}")
        
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        if not service:
            log_info("load_period_from_drive: Drive service not initialized")
            return None
        
        folder_id = _get_major_folder_id_internal()
        
        if not folder_id:
            log_info("load_period_from_drive: no folder_id found")
            return None
        
        log_info(f"Looking for {PERIOD_FILENAME} in folder_id: {folder_id}")
        file_id = gd.find_file_in_drive(service, PERIOD_FILENAME, folder_id)
        if not file_id:
            log_info(f"{PERIOD_FILENAME} not found in Drive")
            return None
        
        payload = gd.download_file_from_drive(service, file_id)
        period = json.loads(payload.decode("utf-8"))
        
        log_info(f"✓ Successfully loaded period from Drive: {period.get('period_id', 'unknown')}")
        return period
    except Exception as e:
        log_error(f"Failed to load period from Drive", e)
        import traceback
        log_error(f"Traceback: {traceback.format_exc()}", Exception("Stack trace"))
        return None


def save_period_to_drive(period: Dict[str, Any]) -> bool:
    """Save current period to Drive for current major."""
    try:
        major = st.session_state.get("current_major", "DEFAULT")
        log_info(f"Attempting to save period to Drive for major {major}: {period.get('period_id', 'unknown')}")
        
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        if not service:
            log_error("save_period_to_drive: Drive service not initialized", Exception("No service"))
            return False
        
        folder_id = _get_major_folder_id_internal()
        
        if not folder_id:
            log_error("save_period_to_drive: no folder_id", Exception("No folder ID"))
            return False
        
        log_info(f"Saving to folder_id: {folder_id}")
        payload = json.dumps(period, indent=2).encode("utf-8")
        gd.sync_file_with_drive(service, payload, PERIOD_FILENAME, "application/json", folder_id)
        
        log_info(f"✓ Successfully saved period to Drive: {period.get('period_id', 'unknown')}")
        return True
    except Exception as e:
        log_error(f"Failed to save period to Drive", e)
        import traceback
        log_error(f"Traceback: {traceback.format_exc()}", Exception("Stack trace"))
        return False


def set_current_period(period: Dict[str, Any]) -> bool:
    """
    Set an existing period as the current period.
    
    Args:
        period: Period dict to set as current
    
    Returns:
        True if successful, False otherwise
    """
    major = st.session_state.get("current_major", "DEFAULT")
    
    # Save to session state
    if "current_periods" not in st.session_state:
        st.session_state.current_periods = {}
    st.session_state.current_periods[major] = period
    
    # Save to Drive
    success = save_period_to_drive(period)
    
    log_info(f"Set current period: {period.get('period_id', 'unknown')}")
    return success


def start_new_period(semester: str, year: int, advisor_name: str) -> tuple[Dict[str, Any], bool]:
    """
    Start a new advising period. Archives current period to history.
    
    Args:
        semester: Fall, Spring, or Summer
        year: Year of the period
        advisor_name: Name of the advisor
    
    Returns:
        Tuple of (new period dict, drive_saved flag)
    """
    major = st.session_state.get("current_major", "DEFAULT")
    
    # Get current period to archive
    current_period = get_current_period()
    
    # Add to history
    _archive_period_to_history(current_period)
    
    # Create new period
    period_id = f"{semester}_{year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    new_period = {
        "period_id": period_id,
        "semester": semester,
        "year": year,
        "advisor_name": advisor_name,
        "created_at": datetime.now().isoformat(),
    }
    
    # Save to session state and Drive
    if "current_periods" not in st.session_state:
        st.session_state.current_periods = {}
    st.session_state.current_periods[major] = new_period

    # Clear all advising selections so we start fresh for the new period
    st.session_state.advising_selections = {}
    if "majors" in st.session_state and major in st.session_state.majors:
        st.session_state.majors[major]["advising_selections"] = {}

    # Clear per-major bypasses
    bypasses_key = f"bypasses_{major}"
    if bypasses_key in st.session_state:
        st.session_state[bypasses_key] = {}

    # Delete the local selections cache file so stale data isn't reloaded
    try:
        from advising_history import _get_local_selections_path
        import os
        selections_file = _get_local_selections_path(major)
        if os.path.exists(selections_file):
            os.remove(selections_file)
    except Exception as e:
        log_error("Failed to clear local selections cache on new period", e)

    # Clear session-loaded flags so the new period loads fresh
    # Also clear per-student widget keys (multiselect/note) and auto-load flags so that
    # the new period starts with completely empty selections — without this, Streamlit
    # widget keys bound to st.session_state retain the previous period's values even
    # after advising_selections is cleared.
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and (
            key.startswith("_fsv_sessions_loaded_") or
            key.startswith("_sessions_loaded_") or
            key.startswith("_fsv_cache_") or
            key.startswith("advised_ms_") or
            key.startswith("optional_ms_") or
            key.startswith("repeat_ms_") or
            key.startswith("note_") or
            key.startswith("_autoloaded_") or
            key.startswith("_eligibility_cache_") or
            key.startswith("_student_data_hash_")
        ):
            del st.session_state[key]

    drive_saved = save_period_to_drive(new_period)

    log_info(f"Started new period: {period_id}")
    return new_period, drive_saved


def _archive_period_to_history(period: Dict[str, Any]) -> None:
    """Archive a period to the history file in Drive."""
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        folder_id = _get_major_folder_id_internal()
        major = st.session_state.get("current_major", "DEFAULT")

        if not folder_id:
            return

        # Load existing history
        history = []
        file_id = gd.find_file_in_drive(service, PERIODS_HISTORY_FILENAME, folder_id)
        if file_id:
            try:
                payload = gd.download_file_from_drive(service, file_id)
                history = json.loads(payload.decode("utf-8"))
                if not isinstance(history, list):
                    history = []
            except:
                history = []
        
        # Add current period to history (avoid duplicates)
        period_id = period.get("period_id", "")
        if period_id and not any(p.get("period_id") == period_id for p in history):
            period_copy = period.copy()
            period_copy["archived_at"] = datetime.now().isoformat()
            history.append(period_copy)
        
        # Save updated history
        payload = json.dumps(history, indent=2).encode("utf-8")
        gd.sync_file_with_drive(service, payload, PERIODS_HISTORY_FILENAME, "application/json", folder_id)

        if "period_history_cache" not in st.session_state:
            st.session_state.period_history_cache = {}
        st.session_state.period_history_cache[major] = history

        log_info(f"Archived period to history: {period_id}")
    except Exception as e:
        log_error(f"Failed to archive period to history", e)


def _merge_period_entries(existing: Dict[str, Any], new_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two period records, preserving archived metadata when available."""

    merged = existing.copy()
    merged.update({k: v for k, v in new_entry.items()})

    archived_at = new_entry.get("archived_at") or existing.get("archived_at")
    if archived_at:
        merged["archived_at"] = archived_at

    # Ensure we keep the latest created_at timestamp if both exist
    created_existing = existing.get("created_at", "")
    created_new = new_entry.get("created_at", "")
    if created_new and created_new > created_existing:
        merged["created_at"] = created_new
    elif created_existing and not created_new:
        merged["created_at"] = created_existing

    return merged


def get_all_periods(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Get all periods (current + history) for the current major.
    Returns list sorted by creation date (newest first).
    Uses cache to avoid repeated Drive calls. Set force_refresh=True to reload from Drive.
    """
    major = st.session_state.get("current_major", "DEFAULT")

    if "period_history_cache" not in st.session_state:
        st.session_state.period_history_cache = {}

    cached_history: List[Dict[str, Any]] = st.session_state.period_history_cache.get(major, [])
    
    # Use cache if available (unless force refresh)
    if not force_refresh and cached_history:
        history = cached_history
    else:
        history = []
        try:
            gd = _get_drive_module()
            service = gd.initialize_drive_service()
            folder_id = _get_major_folder_id_internal()

            if service and folder_id:
                file_id = gd.find_file_in_drive(service, PERIODS_HISTORY_FILENAME, folder_id)
                if file_id:
                    payload = gd.download_file_from_drive(service, file_id)
                    history_payload = json.loads(payload.decode("utf-8"))
                    if isinstance(history_payload, list):
                        history = history_payload
                        st.session_state.period_history_cache[major] = history
        except Exception as e:
            log_error(f"Failed to load period history", e)
            history = cached_history

    combined_periods: List[Dict[str, Any]] = []

    current = get_current_period()
    if current:
        combined_periods.append(current)

    combined_periods.extend(history)
    
    # Reconstruct missing periods from advising sessions
    # This recovers periods that have session data but are missing from history
    reconstructed = _reconstruct_periods_from_sessions()
    combined_periods.extend(reconstructed)

    unique_periods: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    for period in combined_periods:
        period_id = period.get("period_id")
        if not period_id:
            # If there is no period_id, treat as unique by object id to avoid collisions
            period_id = f"__unnamed__{id(period)}"

        if period_id in unique_periods:
            unique_periods[period_id] = _merge_period_entries(unique_periods[period_id], period)
        else:
            unique_periods[period_id] = period.copy()
            order.append(period_id)

    deduped_periods = [unique_periods[pid] for pid in order]
    deduped_periods.sort(key=lambda p: p.get("created_at", ""), reverse=True)

    return deduped_periods
