# app.py - Advising Dashboard with Modern UI

import os
import pandas as pd
import streamlit as st
from datetime import datetime

from auth import (
    load_auth_config,
    auth_is_enforced,
    is_authenticated_for_major,
    set_authenticated_for_major,
    render_login_gate,
)
from visual_theme import apply_visual_theme
from advising_utils import log_info, log_error, load_progress_excel

def _get_drive_module():
    """Lazy loader for google_drive module to avoid import-time side effects."""
    import google_drive as gd
    return gd

st.set_page_config(
    page_title="Advising Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

apply_visual_theme()

MAJORS = ["PBHL", "SPTH-New", "SPTH-Old", "NURS"]

if "majors" not in st.session_state:
    st.session_state.majors = {
        m: {
            "courses_df": pd.DataFrame(),
            "progress_df": pd.DataFrame(),
            "advising_selections": {},
        }
        for m in MAJORS
    }

def _sync_globals_from_bucket(major: str):
    """Sync global session state from major bucket."""
    bucket = st.session_state.majors.get(major, {})
    st.session_state.courses_df = bucket.get("courses_df", pd.DataFrame())
    st.session_state.progress_df = bucket.get("progress_df", pd.DataFrame())
    st.session_state.advising_selections = bucket.get("advising_selections", {})

def _sync_bucket_from_globals(major: str):
    """Sync major bucket from global session state."""
    if major not in st.session_state.majors:
        st.session_state.majors[major] = {}
    bucket = st.session_state.majors[major]
    bucket["courses_df"] = st.session_state.get("courses_df", pd.DataFrame())
    bucket["progress_df"] = st.session_state.get("progress_df", pd.DataFrame())
    bucket["advising_selections"] = st.session_state.get("advising_selections", {})

def _default_period_for_today() -> tuple:
    """Return default semester and year based on current date."""
    today = datetime.now()
    month = today.month
    year = today.year
    if month == 1:
        return "Fall", year - 1
    if 2 <= month <= 6:
        return "Spring", year
    if 7 <= month <= 9:
        return "Summer", year
    return "Fall", year

def _count_advised_from_index(progress_ids = None) -> int:
    """Count students with saved sessions from the advising index (fast, no payload download).
    
    Args:
        progress_ids: Optional set of student IDs from progress report to filter against.
                     Only counts students that are in this set if provided.
    """
    try:
        from advising_period import get_current_period
        from advising_history import _load_index
        
        # _load_index() has internal per-major caching via _advising_index_cache_{major}
        index = _load_index()
        
        current_period = get_current_period()
        period_id = current_period.get("period_id", "")
        if not period_id:
            return 0
            
        # If we have progress_ids but index is empty, try one force refresh 
        # to ensure we're not seeing a stale cache from before Drive was ready
        if not index and progress_ids:
             index = _load_index(force_refresh=True)
        
        if not index:
            return 0
        
        # Count unique students with sessions in this period
        students_with_sessions = set()
        for entry in index:
            if str(entry.get("period_id", "")) == str(period_id):
                sid = entry.get("student_id")
                if sid:
                    # Normalize to int for comparison
                    try:
                        norm_sid = int(sid)
                    except (ValueError, TypeError):
                        norm_sid = sid
                    
                    # Filter to students in progress report if provided
                    if progress_ids is None or norm_sid in progress_ids:
                        students_with_sessions.add(norm_sid)
        
        return len(students_with_sessions)
    except Exception as e:
        log_error("Dashboard count failed", e)
        return 0

def _render_header():
    """Render the persistent header with major/period selection."""
    from advising_period import get_current_period
    
    current_major = st.session_state.get("current_major", "Select major...")
    if current_major in MAJORS:
        auth_cfg = load_auth_config()
        auth_enforced = auth_is_enforced(auth_cfg)
        is_major_authed = (not auth_enforced) or is_authenticated_for_major(current_major)
    else:
        is_major_authed = True
    
    header_cols = st.columns([1, 2, 3, 2])
    
    with header_cols[0]:
        if os.path.exists("pu_logo.png"):
            st.image("pu_logo.png", width=80)
    
    with header_cols[1]:
        major_options = ["Select major..."] + MAJORS
        current = st.session_state.get("current_major", "Select major...")
        if current not in major_options:
            current = "Select major..."
        
        selected_major = st.selectbox(
            "Major",
            major_options,
            index=major_options.index(current),
            key="header_major_select",
            label_visibility="collapsed"
        )
        
        if selected_major != st.session_state.get("current_major"):
            st.session_state["current_major"] = selected_major
            if selected_major in MAJORS:
                _sync_globals_from_bucket(selected_major)
            st.rerun()
    
    with header_cols[2]:
        if st.session_state.get("current_major") in MAJORS:
            if is_major_authed:
                current_period = get_current_period()
                period_text = f"📅 {current_period.get('semester', 'No period')} {current_period.get('year', '')} — {current_period.get('advisor_name', 'Not set')}"
                st.markdown(f"**{period_text}**")
            else:
                st.markdown("🔒 **Login required**")
        else:
            st.markdown("*Select a major to begin*")
    
    with header_cols[3]:
        if st.session_state.get("current_major") in MAJORS:
            top_left, top_right = st.columns([3, 2])
            with top_left:
                if is_major_authed:
                    progress_df = st.session_state.get("progress_df", pd.DataFrame())
                    if not progress_df.empty:
                        total = len(progress_df)
                        # Get student IDs from progress report for filtering
                        progress_ids = set()
                        for _, row in progress_df.iterrows():
                            try:
                                progress_ids.add(int(row.get("ID", 0)))
                            except (ValueError, TypeError):
                                pass
                        
                        # Count students with saved sessions (from index, filtered to current roster)
                        advised = _count_advised_from_index(progress_ids)
                            
                        pct = int(advised / total * 100) if total > 0 else 0
                        st.markdown(f"**Progress:** {advised}/{total} ({pct}%)")
            with top_right:
                major = st.session_state.get("current_major", "")
                if major in MAJORS and is_major_authed and st.button("Logout", key=f"logout_{major}"):
                    set_authenticated_for_major(major, False)
                    st.rerun()

def _render_navigation():
    """Render the main navigation tabs."""
    
    nav_options = ["Home", "Setup", "Workspace", "Insights", "Settings"]
    
    if "nav_selection" not in st.session_state:
        st.session_state["nav_selection"] = "Home"
    elif st.session_state["nav_selection"] not in nav_options:
        st.session_state["nav_selection"] = "Home"
    
    cols = st.columns(len(nav_options))
    
    for i, option in enumerate(nav_options):
        with cols[i]:
            is_active = st.session_state.get("nav_selection") == option
            btn_type = "primary" if is_active else "secondary"
            
            icons = {"Home": "🏠", "Setup": "⚙️", "Workspace": "👤", "Insights": "📊", "Settings": "🔧"}
            
            if st.button(
                f"{icons.get(option, '')} {option}",
                key=f"nav_{option}",
                type=btn_type
            ):
                st.session_state["nav_selection"] = option
                st.rerun()
    
    return st.session_state.get("nav_selection", "Home")

def _render_period_gate():
    """Render period selection gate for first-time setup."""
    from advising_period import get_current_period, start_new_period, get_all_periods, set_current_period
    
    current_period = get_current_period()
    all_periods = get_all_periods()
    major = st.session_state.get("current_major", "")
    
    if current_period.get("advisor_name", "").strip():
        return True
    
    st.markdown("## Welcome! Let's set up your advising period.")
    st.markdown("Before you begin, please select or create an advising period.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Create New Period")
        
        with st.form("new_period_gate"):
            default_semester, default_year = _default_period_for_today()
            
            semester = st.selectbox("Semester", ["Fall", "Spring", "Summer"],
                                   index=["Fall", "Spring", "Summer"].index(default_semester))
            year = st.number_input("Year", min_value=2020, max_value=2099, value=default_year)
            advisor = st.text_input("Your Name")
            
            if st.form_submit_button("Start Period", type="primary"):
                if not advisor:
                    st.error("Please enter your name")
                else:
                    new_period, saved = start_new_period(semester, int(year), advisor)
                    # start_new_period clears all selections; just show confirmation
                    st.success(f"Created: {semester} {year}")
                    st.rerun()
    
    with col2:
        st.markdown("### Use Existing Period")
        
        real_periods = [p for p in all_periods if p.get("advisor_name", "").strip()]
        
        if real_periods:
            period_options = []
            period_map = {}
            for p in real_periods:
                label = f"{p.get('semester', '')} {p.get('year', '')} — {p.get('advisor_name', '')}"
                period_options.append(label)
                period_map[label] = p
            
            selected = st.selectbox("Select Period", period_options)
            
            if st.button("Use This Period"):
                selected_period = period_map[selected]
                set_current_period(selected_period)
                # Clear selections so we load the correct sessions for this period
                major = st.session_state.get("current_major", "")
                st.session_state.advising_selections = {}
                if "majors" in st.session_state and major in st.session_state.majors:
                    st.session_state.majors[major]["advising_selections"] = {}
                bypasses_key = f"bypasses_{major}"
                if bypasses_key in st.session_state:
                    st.session_state[bypasses_key] = {}
                try:
                    from advising_history import _get_local_selections_path
                    import os
                    sel_file = _get_local_selections_path(major)
                    if os.path.exists(sel_file):
                        os.remove(sel_file)
                except Exception:
                    pass
                for key in list(st.session_state.keys()):
                    if isinstance(key, str) and (
                        key.startswith("_fsv_sessions_loaded_") or
                        key.startswith("_sessions_loaded_") or
                        key.startswith("_fsv_cache_")
                    ):
                        del st.session_state[key]
                st.success(f"Using: {selected}")
                st.rerun()
        else:
            st.info("No existing periods. Create a new one to get started.")
    
    return False

def _auto_load_from_drive(major: str):
    """Auto-load data files from Google Drive for the selected major."""
    from io import BytesIO
    
    load_key = f"_loaded_{major}"
    if st.session_state.get(load_key):
        return
    
    if not st.session_state.courses_df.empty and not st.session_state.progress_df.empty:
        st.session_state[load_key] = True
        return
    
    root_folder_id = ""
    try:
        if "google" in st.secrets:
            root_folder_id = st.secrets["google"].get("folder_id", "")
    except:
        pass
    if not root_folder_id:
        root_folder_id = os.getenv("GOOGLE_FOLDER_ID", "")
    
    if not root_folder_id:
        return
    
    try:
        gd = _get_drive_module()
        service = gd.initialize_drive_service()
        if not service:
            return
        
        major_folder_id = gd.get_major_folder_id(service, major, root_folder_id)
        
        if st.session_state.courses_df.empty:
            file_id = gd.find_file_in_drive(service, "courses_table.xlsx", major_folder_id)
            if file_id:
                data = gd.download_file_from_drive(service, file_id)
                if data:
                    st.session_state.courses_df = pd.read_excel(BytesIO(data))
                    st.session_state.majors[major]["courses_df"] = st.session_state.courses_df
                    log_info(f"Loaded courses from Drive for {major}")
        
        if st.session_state.progress_df.empty:
            file_id = gd.find_file_in_drive(service, "progress_report.xlsx", major_folder_id)
            if file_id:
                data = gd.download_file_from_drive(service, file_id)
                if data:
                    st.session_state.progress_df = load_progress_excel(data)
                    st.session_state.majors[major]["progress_df"] = st.session_state.progress_df
                    log_info(f"Loaded progress from Drive for {major}")
        
        st.session_state[load_key] = True
    except Exception as e:
        log_error(f"Auto-load from Drive failed for {major}", e)

def main():
    """Main application entry point."""
    # 1. Render Header first (major selection happens here)
    _render_header()
    
    st.markdown("---")
    
    # 2. Read selected major after header interaction
    selected_major = st.session_state.get("current_major", "Select major...")
    
    # 3. Major selection gate
    if selected_major not in MAJORS:
        st.markdown("## 🎓 Advising Dashboard")
        st.info("👆 Please select a major from the dropdown above to get started.")
        
        st.markdown("### Quick Start")
        st.markdown("""
        1. **Select a major** from the dropdown above
        2. **Enter major password** to unlock access
        3. **Set up your advising period** (semester, year, your name)
        4. **Upload data files** (courses table and progress report)
        5. **Start advising** students in the Workspace
        """)
        return

    # 4. Auth gate (before loading/rendering protected content)
    auth_cfg = load_auth_config()
    if auth_is_enforced(auth_cfg):
        if not render_login_gate(selected_major, auth_cfg):
            return

    # 5. Initialize major context and sync data buckets only after auth passes
    if selected_major in MAJORS:
        _sync_globals_from_bucket(selected_major)
        
        # Auto-load from Drive if bucket is empty
        bucket = st.session_state.majors.get(selected_major, {})
        if bucket.get("courses_df", pd.DataFrame()).empty or bucket.get("progress_df", pd.DataFrame()).empty:
            _auto_load_from_drive(selected_major)

    # 6. Render period gate if needed
    if not _render_period_gate():
        return
    
    # 7. Session index is already loaded/refreshed by _count_advised_from_index()
    # in header or by specialized views.
    active_nav = _render_navigation()
    
    st.markdown("---")
    
    if active_nav == "Home":
        from pages.home import render_home
        render_home()
    
    elif active_nav == "Setup":
        from pages.setup import render_setup
        render_setup()
    
    elif active_nav == "Workspace":
        from pages.workspace import render_workspace
        render_workspace()
    
    elif active_nav == "Insights":
        from pages.insights import render_insights
        render_insights()
    
    elif active_nav == "Settings":
        from pages.settings import render_settings
        render_settings()
    
    _sync_bucket_from_globals(selected_major)

if __name__ == "__main__":
    main()
