import streamlit as st
import pandas as pd
from datetime import datetime

def _get_drive_module():
    """Lazy loader for google_drive module."""
    import google_drive as gd
    return gd

def render_settings():
    """Render the Settings page with session management, exclusions, and sync."""
    
    st.markdown("## Settings")
    
    tabs = st.tabs(["Sessions", "Exclusions", "Sync", "Email Templates"])
    
    with tabs[0]:
        _render_session_management()
    
    with tabs[1]:
        _render_exclusions()
    
    with tabs[2]:
        _render_sync_settings()
    
    with tabs[3]:
        _render_email_templates()

def _render_session_management():
    """Render session management section."""
    from advising_period import get_current_period
    from advising_history import _load_session_and_apply
    
    st.markdown("### Session Management")
    
    major = st.session_state.get("current_major", "")
    current_period = get_current_period()
    
    st.markdown(f"**Current Period:** {current_period.get('semester', '')} {current_period.get('year', '')} — {current_period.get('advisor_name', '')}")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Clear Sessions")
        
        if st.button("Clear All Selections", type="secondary"):
            st.session_state.advising_selections = {}
            st.session_state.majors[major]["advising_selections"] = {}
            
            for key in list(st.session_state.keys()):
                if isinstance(key, str) and key.startswith("_autoloaded_"):
                    del st.session_state[key]
            
            if "current_student_id" in st.session_state:
                del st.session_state["current_student_id"]
            if "workspace_selected_student" in st.session_state:
                del st.session_state["workspace_selected_student"]
            
            st.success("Cleared all selections")
            st.rerun()
        
        st.caption("Clears current advising selections. Does not affect saved sessions.")
    
    with col2:
        st.markdown("#### Restore Sessions")
        
        if st.button("Restore All Sessions", type="primary"):
            progress_df = st.session_state.get("progress_df", pd.DataFrame())
            
            if not progress_df.empty and "ID" in progress_df.columns:
                student_ids = progress_df["ID"].unique()
                loaded_count = 0
                
                for sid in student_ids:
                    if f"_autoloaded_{sid}" in st.session_state:
                        del st.session_state[f"_autoloaded_{sid}"]
                    if _load_session_and_apply(sid):
                        loaded_count += 1
                
                st.session_state.majors[major]["advising_selections"] = st.session_state.advising_selections.copy()
                st.success(f"Restored sessions for {loaded_count} students")
                st.rerun()
            else:
                st.warning("No students found. Upload progress report first.")
        
        st.caption("Loads the most recent session for each student.")
    
    st.markdown("---")
    
    st.markdown("#### Bulk Restore")
    
    with st.expander("Select Students to Restore", expanded=False):
        try:
            import advising_history as ah
            if hasattr(ah, "bulk_restore_panel"):
                ah.bulk_restore_panel()
            else:
                st.info("Bulk restore not available")
        except Exception as e:
            st.error(f"Error: {e}")

def _render_exclusions():
    """Render course exclusions management - intensive courses only with bulk student selection."""
    
    st.markdown("### Course Exclusions")
    st.caption("Hide intensive courses from students' eligibility views (bulk or individual)")
    
    progress_df = st.session_state.get("progress_df", pd.DataFrame())
    courses_df = st.session_state.get("courses_df", pd.DataFrame())
    major = st.session_state.get("current_major", "")
    
    if progress_df.empty or courses_df.empty:
        st.info("Upload data files to manage exclusions.")
        return
    
    exclusions_key = f"course_exclusions_{major}"
    if exclusions_key not in st.session_state:
        st.session_state[exclusions_key] = {}
    
    exclusions = st.session_state[exclusions_key]
    
    # Filter to intensive courses only
    intensive_courses = courses_df[courses_df["Type"].astype(str).str.lower() == "intensive"]["Course Code"].tolist()
    
    if not intensive_courses:
        st.info("No intensive courses found in the curriculum.")
        return
    
    student_options = [f"{row['NAME']} ({row['ID']})" for _, row in progress_df.iterrows()]
    
    st.markdown("#### Add Exclusions")
    
    with st.form("add_exclusion"):
        # Select intensive courses first
        selected_courses = st.multiselect(
            "Intensive Courses to Exclude", 
            intensive_courses,
            help="Select intensive courses to hide from selected students"
        )
        
        st.markdown("**Select Students:**")
        
        col1, col2 = st.columns(2)
        with col1:
            select_all = st.checkbox("Select All Students", key="select_all_students")
        
        if select_all:
            selected_students = student_options
            st.caption(f"All {len(student_options)} students selected")
        else:
            selected_students = st.multiselect(
                "Students",
                student_options,
                help="Select one or more students to apply exclusions"
            )
        
        if st.form_submit_button("Add Exclusions", type="primary", help="Apply selected course exclusions to selected students"):
            if selected_courses and selected_students:
                from course_exclusions import set_for_student
                added_count = 0
                for student_label in selected_students:
                    sid = student_label.split("(")[-1].rstrip(")")
                    if sid not in exclusions:
                        exclusions[sid] = []
                    for course in selected_courses:
                        if course not in exclusions[sid]:
                            exclusions[sid].append(course)
                            added_count += 1
                    # Sync to course_exclusions module so workspace picks it up
                    set_for_student(sid, exclusions[sid])
                st.session_state[exclusions_key] = exclusions
                st.success(f"Added {added_count} exclusions across {len(selected_students)} students")
                st.rerun()
            else:
                st.warning("Please select both courses and students")
    
    if exclusions:
        st.markdown("#### Current Exclusions")
        
        # Show summary
        total_exclusions = sum(len(courses) for courses in exclusions.values())
        st.caption(f"Total: {total_exclusions} exclusions across {len(exclusions)} students")
        
        for sid, courses in exclusions.items():
            if courses:
                student_row = progress_df[progress_df["ID"].astype(str) == str(sid)]
                name = student_row.iloc[0]["NAME"] if not student_row.empty else sid
                
                with st.expander(f"{name} — {len(courses)} exclusions"):
                    for course in courses:
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.write(course)
                        with col2:
                            if st.button("Remove", key=f"remove_{sid}_{course}", help="Remove this exclusion"):
                                from course_exclusions import set_for_student
                                exclusions[sid].remove(course)
                                set_for_student(sid, exclusions[sid])
                                st.session_state[exclusions_key] = exclusions
                                st.rerun()

def _render_sync_settings():
    """Render Google Drive sync settings."""
    
    st.markdown("### Google Drive Sync")
    
    major = st.session_state.get("current_major", "")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Refresh Data")
        
        if st.button("🔄 Force Sync from Drive", type="primary"):
            # Clear all caches including local file cache
            from advising_history import load_all_sessions_for_period, _get_local_cache_dir
            import shutil
            import os
            
            # Clear local file cache
            cache_dir = _get_local_cache_dir()
            if os.path.exists(cache_dir):
                try:
                    shutil.rmtree(cache_dir)
                    os.makedirs(cache_dir, exist_ok=True)
                except Exception:
                    pass
            
            # Clear session state caches
            if "period_history_cache" in st.session_state:
                st.session_state.period_history_cache.pop(major, None)
            
            cache_key = f"_advising_index_cache_{major}"
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            
            # Clear advising index
            if "advising_index" in st.session_state:
                del st.session_state["advising_index"]
            
            # Clear advising selections
            if "advising_selections" in st.session_state:
                del st.session_state["advising_selections"]
            
            # Clear sessions loaded flags
            for key in list(st.session_state.keys()):
                if isinstance(key, str) and (
                    key.startswith("_fsv_sessions_loaded_") or 
                    key.startswith("_sessions_loaded_") or
                    key.startswith("_fsv_cache_")
                ):
                    del st.session_state[key]
            
            # Force reload from Drive
            with st.spinner("Syncing from Google Drive..."):
                load_all_sessions_for_period(force_refresh=True)
            
            st.success("✅ Data synced from Google Drive")
            st.rerun()
        
        st.caption("Forces a full refresh from Google Drive and rebuilds local cache")
    
    with col2:
        st.markdown("#### Connection Status")
        
        try:
            gd = _get_drive_module()
            service = gd.initialize_drive_service()
            if service:
                st.success("✓ Connected to Google Drive")
            else:
                st.warning("Not connected")
        except Exception as e:
            st.error(f"Connection error: {str(e)[:50]}")
    
    st.markdown("---")
    
    # Show local cache info
    st.markdown("#### Local Cache Status")
    from advising_history import _get_local_cache_dir, _get_local_index_path, _get_local_selections_path
    import os
    
    cache_dir = _get_local_cache_dir()
    index_path = _get_local_index_path(major)
    selections_path = _get_local_selections_path(major)
    
    col_cache1, col_cache2 = st.columns(2)
    with col_cache1:
        if os.path.exists(index_path):
            mod_time = datetime.fromtimestamp(os.path.getmtime(index_path))
            st.success(f"✓ Index cache: {mod_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            st.info("No index cache")
    
    with col_cache2:
        if os.path.exists(selections_path):
            mod_time = datetime.fromtimestamp(os.path.getmtime(selections_path))
            st.success(f"✓ Selections cache: {mod_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            st.info("No selections cache")
    
    st.caption("Local cache enables instant page loading")
    
    st.markdown("---")
    
    st.markdown("#### Drive Folder Configuration")
    
    import os as os_module
    
    folder_id = ""
    try:
        if "google" in st.secrets:
            folder_id = st.secrets["google"].get("folder_id", "")
    except:
        pass
    if not folder_id:
        folder_id = os_module.getenv("GOOGLE_FOLDER_ID", "")
    
    if folder_id:
        st.text_input("Root Folder ID", value=folder_id, disabled=True)
        st.caption(f"Files are organized in: {folder_id}/{major}/")
    else:
        st.warning("No Google Drive folder configured")
        st.caption("Set GOOGLE_FOLDER_ID in your environment or secrets")


def _render_email_templates():
    """Render email template editor with live preview."""
    from advising_period import get_current_period
    
    st.subheader("📧 Email Template")
    st.markdown("Edit the email template and see a live preview of how it will look.")
    
    current_period = get_current_period()
    period_id = current_period.get("period_id", "default")
    
    # Template editor
    st.markdown("**Email Header (appears before course list):**")
    
    # Initialize default template if not exists
    template_key = f"_email_template_{period_id}"
    if template_key not in st.session_state:
        st.session_state[template_key] = """Dear {student_name},

Based on your academic progress and requirements, here are your recommended courses for {semester} {year}:"""
    
    template_text = st.text_area(
        "Edit template",
        value=st.session_state[template_key],
        height=150,
        label_visibility="collapsed",
        help="Variables: {student_name}, {semester}, {year}, {advisor_name}"
    )
    
    if template_text != st.session_state[template_key]:
        st.session_state[template_key] = template_text
    
    st.markdown("**Available variables:**")
    st.code("{student_name} - Student full name\n{semester} - Current semester\n{year} - Current year\n{advisor_name} - Advisor name", language="text")
    
    st.divider()
    
    # Live preview
    st.markdown("**📧 Email Preview:**")
    
    # Mock data
    mock_student_name = "Sarah Johnson"
    mock_semester = current_period.get("semester", "Spring")
    mock_year = current_period.get("year", "2025")
    mock_advisor = current_period.get("advisor_name", "Dr. Smith")
    
    # Fill in template variables
    preview_header = template_text.format(
        student_name=mock_student_name,
        semester=mock_semester,
        year=mock_year,
        advisor_name=mock_advisor
    )
    
    # Build mock email content
    mock_email = f"""{preview_header}

ADVISED COURSES:
┌─────────────────────────────────────────────────────┐
│ CS 201 - Data Structures (4 cr)                     │
│ MATH 301 - Linear Algebra (3 cr)                    │
│ PHYS 201 - Physics II (4 cr)                        │
│ ENG 210 - English Composition (3 cr)                │
└─────────────────────────────────────────────────────┘

OPTIONAL COURSES:
┌─────────────────────────────────────────────────────┐
│ CHEM 150 - General Chemistry (4 cr)                 │
│ ELEC 101 - Introduction to Electronics (3 cr)       │
└─────────────────────────────────────────────────────┘

REPEAT COURSES (to improve GPA):
┌─────────────────────────────────────────────────────┐
│ CS 101 - Introduction to Programming (3 cr)         │
└─────────────────────────────────────────────────────┘

ADVISOR NOTE:
Focus on completing core requirements this semester. 
Your progress is on track for graduation in Spring 2027/2028.

---
Advisor: {mock_advisor}
Academic Year: {mock_year}/{int(mock_year) + 1}
"""
    
    # Display preview in a styled box
    st.markdown(
        f"""
        <div style='background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 8px; padding: 16px; font-family: monospace; white-space: pre-wrap; line-height: 1.6;'>
        {mock_email}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.divider()
    
    st.markdown("**Current Period Info:**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.text(f"Semester: {current_period.get('semester', 'N/A')}")
    with col2:
        st.text(f"Year: {current_period.get('year', 'N/A')}")
    with col3:
        st.text(f"Advisor: {current_period.get('advisor_name', 'N/A')}")
    with col4:
        if st.button("Reset to Default", type="secondary", help="Restore default email template"):
            st.session_state[template_key] = """Dear {student_name},

Based on your academic progress and requirements, here are your recommended courses for {semester} {year}:"""
            st.rerun()


