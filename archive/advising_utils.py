# utils.py

import streamlit as st
import pandas as pd
import logging
import hashlib
from io import BytesIO
from typing import List, Tuple, Dict, Any, Union, Optional

# Import eligibility functions from standalone module to prevent circular imports
from eligibility_utils import (
    check_course_completed,
    check_course_registered,
    get_student_standing,
    parse_requirements,
    is_course_offered,
    build_requisites_str,
    get_corequisite_and_concurrent_courses,
    get_mutual_concurrent_pairs,
    check_eligibility,
)


# ------------- Cached wrapper functions for performance ---------------

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_mutual_pairs(_courses_df_hash: str, courses_df: pd.DataFrame) -> Dict[str, List[str]]:
    """Cached wrapper for get_mutual_concurrent_pairs. Uses hash of DataFrame for cache key."""
    return get_mutual_concurrent_pairs(courses_df)


@st.cache_data(ttl=300)  # Cache for 5 minutes  
def get_cached_coreq_concurrent(_courses_df_hash: str, courses_df: pd.DataFrame) -> List[str]:
    """Cached wrapper for get_corequisite_and_concurrent_courses. Uses hash of DataFrame for cache key."""
    return get_corequisite_and_concurrent_courses(courses_df)


def _hash_dataframe(df: pd.DataFrame) -> str:
    """Create a hash of a DataFrame for cache key purposes."""
    if df is None or df.empty:
        return "empty"
    try:
        return hashlib.md5(pd.util.hash_pandas_object(df).values.tobytes()).hexdigest()
    except Exception:
        return hashlib.md5(str(df.shape).encode()).hexdigest()


def get_mutual_pairs_cached(courses_df: pd.DataFrame) -> Dict[str, List[str]]:
    """Get mutual concurrent pairs with caching."""
    df_hash = _hash_dataframe(courses_df)
    return get_cached_mutual_pairs(df_hash, courses_df)


def get_coreq_concurrent_cached(courses_df: pd.DataFrame) -> List[str]:
    """Get corequisite and concurrent courses with caching."""
    df_hash = _hash_dataframe(courses_df)
    return get_cached_coreq_concurrent(df_hash, courses_df)

# Re-export for backward compatibility
__all__ = [
    "check_course_completed",
    "check_course_registered", 
    "get_student_standing",
    "parse_requirements",
    "is_course_offered",
    "build_requisites_str",
    "get_corequisite_and_concurrent_courses",
    "get_mutual_concurrent_pairs",
    "check_eligibility",
    "style_df",
    "load_progress_excel",
    "log_info",
    "log_error",
    "get_major_folder_id_helper",
    "get_student_selections",
    "get_student_bypasses",
    # Cached versions
    "get_mutual_pairs_cached",
    "get_coreq_concurrent_cached",
    "_hash_dataframe",
]

# ---------------- Logging ----------------

logging.basicConfig(
    filename="app.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

def get_student_selections(student_id: Union[int, str]) -> Dict[str, Any]:
    """Robustly fetch advising selections for a student from session state."""
    if "advising_selections" not in st.session_state:
        return {"advised": [], "optional": [], "repeat": [], "note": ""}
    
    sels = st.session_state.advising_selections
    sid_str = str(student_id)
    sid_int = int(student_id) if sid_str.isdigit() else None
    
    slot = (
        sels.get(student_id)
        or sels.get(sid_str)
        or (sels.get(sid_int) if sid_int is not None else None)
        or {"advised": [], "optional": [], "repeat": [], "note": ""}
    )
    
    # Ensure all keys exist
    for key in ["advised", "optional", "repeat"]:
        if key not in slot:
            slot[key] = []
    if "note" not in slot:
        slot["note"] = ""
        
    return slot

def get_student_bypasses(student_id: Union[int, str], major: str) -> Dict[str, Any]:
    """Robustly fetch bypasses for a student from session state."""
    bypasses_key = f"bypasses_{major}"
    if bypasses_key not in st.session_state:
        return {}
    
    all_bypasses = st.session_state[bypasses_key]
    sid_str = str(student_id)
    sid_int = int(student_id) if sid_str.isdigit() else None
    
    return (
        all_bypasses.get(student_id)
        or all_bypasses.get(sid_str)
        or (all_bypasses.get(sid_int) if sid_int is not None else None)
        or {}
    )

def log_info(message: str) -> None:
    try:
        logger.info(message)
    except Exception:
        pass

def log_error(message: str, error: Union[Exception, str]) -> None:
    try:
        logger.error(f"{message}: {error}", exc_info=isinstance(error, Exception))
    except Exception:
        pass

def get_major_folder_id_helper(service) -> str:
    """Centralized helper to get major-specific folder ID from secrets or env."""
    import os
    major = st.session_state.get("current_major", "DEFAULT")
    root_folder_id = ""
    try:
        if "google" in st.secrets:
            root_folder_id = st.secrets["google"].get("folder_id", "")
    except Exception:
        pass
    
    if not root_folder_id:
        root_folder_id = os.getenv("GOOGLE_FOLDER_ID", "")
    
    if not root_folder_id:
        return ""
    
    import google_drive as gd
    return gd.get_major_folder_id(service, major, root_folder_id)




# ------------- Styling for Streamlit tables --------------

def style_df(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    def _row_style(row):
        val = str(row.get("Action") or row.get("Eligibility Status") or "").lower()
        color = ""
        if "completed" in val:
            color = "#D5E8D4"  # green
        elif "advised" in val:
            color = "#FFF2CC"  # yellow
        elif "registered" in val:
            color = "#BDD7EE"  # blue
        elif "eligible (not chosen)" in val or val == "eligible":
            color = "#E1F0FF"  # light blue
        elif "not eligible" in val:
            color = "#F8CECC"  # red
        return [f"background-color: {color}"] * len(row)

    styled = df.style.apply(_row_style, axis=1)
    styled = styled.set_table_styles([{
        "selector": "th",
        "props": [("text-align", "left"), ("font-weight", "bold")]
    }])
    return styled


# ------------- Progress loader (merges Intensive sheet) ------------------

_BASE_ID_NAME = ["ID", "NAME"]
_NUMERIC_PREFS = ["# of Credits Completed", "# Registered", "# Remaining", "Total Credits"]

def _coalesce(a: Optional[pd.Series], b: Optional[pd.Series]):
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    # Filter out empty/null entries before combine_first to avoid FutureWarning
    a_filtered = a.dropna() if hasattr(a, 'dropna') else a
    b_filtered = b.dropna() if hasattr(b, 'dropna') else b
    if len(a_filtered) == 0:
        return b
    if len(b_filtered) == 0:
        return a
    return a.combine_first(b)

def load_progress_excel(content: Union[bytes, BytesIO, str]) -> pd.DataFrame:
    """
    Load a progress report that may have two sheets:
      - 'Required Courses'
      - 'Intensive Courses'
    Returns a single DataFrame with all course columns merged on (ID, NAME).
    Works with bytes, BytesIO, or a file path.
    """
    io_obj = BytesIO(content) if isinstance(content, (bytes, bytearray)) else content
    sheets = pd.read_excel(io_obj, sheet_name=None)
    # Pick required/intensive by name; fallbacks if names differ slightly
    req_key = next((k for k in sheets.keys() if "required" in k.lower()), None)
    int_key = next((k for k in sheets.keys() if "intensive" in k.lower()), None)

    if req_key is None:
        # Fallback: take the first as "required"
        req_key = list(sheets.keys())[0]
    req_df = sheets[req_key].copy()

    if int_key is None:
        # No Intensive sheet -> return required only
        return req_df

    int_df = sheets[int_key].copy()

    # Make sure ID/NAME exist
    for col in _BASE_ID_NAME:
        if col not in req_df.columns:
            req_df[col] = None
        if col not in int_df.columns:
            int_df[col] = None

    # Separate course columns
    def course_cols(df: pd.DataFrame) -> List[str]:
        return [c for c in df.columns if c not in _BASE_ID_NAME + _NUMERIC_PREFS]

    req_courses = course_cols(req_df)
    int_courses = course_cols(int_df)

    # Merge on ID/NAME (outer, to be safe)
    merged = pd.merge(
        req_df[_BASE_ID_NAME + req_courses + [c for c in _NUMERIC_PREFS if c in req_df.columns]],
        int_df[_BASE_ID_NAME + int_courses + [c for c in _NUMERIC_PREFS if c in int_df.columns]],
        on=_BASE_ID_NAME,
        how="outer",
        suffixes=("", "_int"),
    )

    # Coalesce numeric preference columns (prefer Required sheet values)
    for col in _NUMERIC_PREFS:
        a = merged[col] if col in merged.columns else None
        b = merged[f"{col}_int"] if f"{col}_int" in merged.columns else None
        out = _coalesce(a, b)
        if out is not None:
            merged[col] = out
        # Drop the *_int helper if it exists
        if f"{col}_int" in merged.columns:
            merged.drop(columns=[f"{col}_int"], inplace=True, errors="ignore")

    return merged

