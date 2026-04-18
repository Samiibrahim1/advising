# eligibility_view.py
from __future__ import annotations

import streamlit as st
import pandas as pd
from io import BytesIO
from typing import Dict, List, Any, Tuple
import time
import hashlib

from eligibility_utils import (
    check_course_completed,
    check_course_registered,
    is_course_offered,
    check_eligibility,
    build_requisites_str,
    get_student_standing,
    get_mutual_concurrent_pairs,
)
from advising_utils import (
    style_df,
    log_info,
    log_error,
    get_student_selections,
    get_student_bypasses,
    get_mutual_pairs_cached,
)
from reporting import apply_excel_formatting
from course_exclusions import (
    ensure_loaded as ensure_exclusions_loaded,
    get_for_student,
    set_for_student,
)
from advising_history import save_session_for_student, _load_session_and_apply
from student_search import render_student_search
from notification_system import show_notification, show_action_feedback
from advising_period import get_current_period


# ---------- helpers ----------

def _norm_id(v: Any):
    """Prefer int IDs; otherwise keep as str."""
    try:
        return int(v)
    except Exception:
        return str(v)


def _sum_credits(codes: List[str]) -> int:
    if not codes:
        return 0
    cdf = st.session_state.courses_df
    if cdf is None or cdf.empty or "Credits" not in cdf.columns:
        return 0
    lookup = cdf.set_index(cdf["Course Code"].astype(str))["Credits"]
    total = 0.0
    for c in codes:
        try:
            total += float(lookup.get(str(c), 0) or 0)
        except Exception:
            pass
    return int(total)


# ---------- Helper functions for UI enhancements ----------

def _format_academic_year(year: str) -> str:
    """Convert year to academic year format. E.g., '2024' -> '2024/2025'"""
    try:
        year_int = int(year)
        return f"{year_int}/{year_int + 1}"
    except (ValueError, TypeError):
        return year


def _build_semester_plan(advised_courses: List[str], optional_courses: List[str], 
                         repeat_courses: List[str], courses_df: pd.DataFrame) -> str:
    """
    Build a semester planning visualization showing which courses are taken when.
    Returns markdown table showing semester offerings.
    """
    if courses_df is None or courses_df.empty:
        return "No course data available"
    
    all_courses = advised_courses + optional_courses + repeat_courses
    if not all_courses:
        return "No courses selected yet"
    
    # Group courses by semester offered
    by_semester = {}
    for course_code in all_courses:
        course_info = courses_df[courses_df["Course Code"] == course_code]
        if not course_info.empty:
            row = course_info.iloc[0]
            semester_offered = str(row.get("Semester Offered", "TBA")).strip()
            if not semester_offered or semester_offered.lower() == "nan":
                semester_offered = "TBA"
            
            # Determine if advised, optional, or repeat
            if course_code in advised_courses:
                course_type = "📌 Advised"
            elif course_code in repeat_courses:
                course_type = "🔄 Repeat"
            else:
                course_type = "📚 Optional"
            
            credits = row.get("Credits", 0)
            title = str(row.get("Title", ""))[:25]  # Truncate for readability
            
            course_display = f"{course_code} - {title} ({credits}cr) {course_type}"
            
            if semester_offered not in by_semester:
                by_semester[semester_offered] = []
            by_semester[semester_offered].append(course_display)
    
    if not by_semester:
        return "No courses selected"
    
    # Build markdown table
    markdown = "| Semester Offered | Courses |\n|---|---|\n"
    for semester in sorted(by_semester.keys(), key=lambda x: (x != "Spring", x != "Fall", x != "Summer", x)):
        courses_list = "<br>".join(by_semester[semester])
        markdown += f"| **{semester}** | {courses_list} |\n"
    
    return markdown


def _format_course_option(course_code: str, courses_df: pd.DataFrame) -> str:
    """Format course code with course information - shows: CODE - Title (Credits cr)"""
    if courses_df is None or courses_df.empty:
        return course_code
    
    course_info = courses_df[courses_df["Course Code"] == course_code]
    if course_info.empty:
        return course_code
    
    row = course_info.iloc[0]
    title = str(row.get("Title", "")).strip()
    credits = row.get("Credits", 0)
    
    # Only include title if available, skip if N/A
    if title and title != "N/A":
        # Format: CODE - Title (Credits cr)
        display_text = f"{course_code} - {title[:30]} ({credits}cr)"
    else:
        # Format: CODE (Credits cr)
        display_text = f"{course_code} ({credits}cr)"
    
    return display_text


def _sum_credits_from_list(course_list: list, courses_df: pd.DataFrame) -> float:
    """Sum credits from a list of course codes."""
    if not course_list or courses_df is None:
        return 0
    total = 0
    for course in course_list:
        course_info = courses_df[courses_df["Course Code"] == course]
        if not course_info.empty:
            try:
                total += float(course_info.iloc[0].get("Credits", 0) or 0)
            except:
                pass
    return total


def _get_recommended_courses(
    eligible_opts: List[str], 
    already_selected: List[str],
    courses_df: pd.DataFrame,
    max_recommendations: int = 3
) -> List[str]:
    """
    Recommend courses based on:
    - Eligibility (already in eligible_opts)
    - Not already selected
    - Prioritize by course type and typical sequence
    """
    recommendations = []
    
    # Filter out already selected courses
    available = [c for c in eligible_opts if c not in already_selected]
    
    if not available:
        return []
    
    # Simple heuristic: prefer courses with matching course codes in sequence
    # Sort by course code to get natural ordering
    available_sorted = sorted(available)
    
    # Return top 3 recommendations
    return available_sorted[:max_recommendations]


# ---------- main panel ----------

def student_eligibility_view():
    """Per-student advising & eligibility with modern UI."""
    if "courses_df" not in st.session_state or st.session_state.courses_df.empty:
        st.warning("Courses table not loaded.")
        return
    if "progress_df" not in st.session_state or st.session_state.progress_df.empty:
        st.warning("Progress report not loaded.")
        return
    if "advising_selections" not in st.session_state:
        st.session_state.advising_selections = {}

    ensure_exclusions_loaded()

    selected_student_id = render_student_search("eligibility")
    
    if selected_student_id is None:
        return
    
    norm_sid = _norm_id(selected_student_id)
    st.session_state["current_student_id"] = norm_sid
    advised_key = f"advised_ms_{norm_sid}"
    optional_key = f"optional_ms_{norm_sid}"
    repeat_key = f"repeat_ms_{norm_sid}"
    note_key = f"note_{norm_sid}"
    
    # Track if student has changed to force refresh from Drive
    prev_student_key = "_prev_student_id_eligibility"
    prev_student = st.session_state.get(prev_student_key)
    student_changed = (prev_student != norm_sid)
    st.session_state[prev_student_key] = norm_sid

    # robust row fetch
    pdf = st.session_state.progress_df
    row = pdf.loc[pdf["ID"] == norm_sid]
    if row.empty:
        row = pdf.loc[pdf["ID"].astype(str) == str(norm_sid)]
    if row.empty:
        st.error(f"Student ID {norm_sid} not found in progress report. Please verify the ID or re-upload the progress report.")
        return
    student_row = row.iloc[0]

    hidden_for_student = set(map(str, get_for_student(norm_sid)))

    # If student changed, force reload their latest session from Drive
    if student_changed:
        from advising_history import reload_student_session_from_drive
        reload_student_session_from_drive(norm_sid)

    # per-student advising slot and bypasses
    slot = get_student_selections(norm_sid)
    st.session_state.advising_selections[norm_sid] = slot
    
    # Auto-load most recent advising session for this student
    # Only load if the slot is empty (all empty lists/strings)
    advised_list = slot.get("advised", [])
    optional_list = slot.get("optional", [])
    repeat_list = slot.get("repeat", [])
    note_val = slot.get("note", "")
    
    is_empty = not (advised_list or optional_list or repeat_list or note_val.strip())
    
    autoloaded_now = False
    if is_empty and f"_autoloaded_{norm_sid}" not in st.session_state:
        if _load_session_and_apply(norm_sid):
            autoloaded_now = True
        st.session_state[f"_autoloaded_{norm_sid}"] = True

    if autoloaded_now:
        slot = get_student_selections(norm_sid)
        st.session_state[advised_key] = list(slot.get("advised", []) or [])
        st.session_state[optional_key] = list(slot.get("optional", []) or [])
        st.session_state[repeat_key] = list(slot.get("repeat", []) or [])
        st.session_state[note_key] = slot.get("note", "")

    major = st.session_state.get("current_major", "")
    student_bypasses = get_student_bypasses(norm_sid, major)

    # header stats
    cr_comp = float(student_row.get("# of Credits Completed", 0) or 0)
    cr_reg = float(student_row.get("# Registered", 0) or 0)
    cr_remaining = float(student_row.get("# Remaining", 0) or 0)
    total_credits = cr_comp + cr_reg
    standing = get_student_standing(total_credits)

    st.markdown(f"### {student_row['NAME']}")
    
    # Calculate advised courses
    advised_list = slot.get("advised", []) or []
    repeat_list = slot.get("repeat", []) or []
    optional_list = slot.get("optional", []) or []
    
    advised_credits = _sum_credits_from_list(advised_list, st.session_state.courses_df)
    repeat_credits = _sum_credits_from_list(repeat_list, st.session_state.courses_df)
    optional_credits = _sum_credits_from_list(optional_list, st.session_state.courses_df)
    
    # Display enhanced metrics
    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
    
    with metric_col1:
        st.metric(
            label="📚 Total Credits",
            value=f"{int(total_credits)}",
            delta=f"{int(cr_remaining)} remaining",
            delta_color="inverse",
            help="Total credits completed / total required"
        )
    
    with metric_col2:
        standing_emoji = "🎓" if standing == "Senior" else "📖" if standing == "Junior" else "🆕"
        st.metric(
            label=f"{standing_emoji} Standing",
            value=standing,
            help="Current academic standing"
        )
    
    with metric_col3:
        total_advised = len(advised_list) + len(repeat_list)
        st.metric(
            label="✅ Advised",
            value=f"{total_advised}",
            delta=f"{int(advised_credits + repeat_credits)} cr",
            delta_color="normal",
            help="Advised courses + repeats this session"
        )
    
    with metric_col4:
        st.metric(
            label="📝 Optional",
            value=f"{len(optional_list)}",
            delta=f"{int(optional_credits)} cr",
            delta_color="normal",
            help="Optional electives available"
        )
    
    with metric_col5:
        pct_complete = int((total_credits / (total_credits + cr_remaining) * 100)) if (total_credits + cr_remaining) > 0 else 0
        st.metric(
            label="📊 Progress",
            value=f"{pct_complete}%",
            delta=f"{int(cr_remaining)} to go",
            delta_color="inverse",
            help="Percentage of degree completed"
        )
    
    # Email status indicator (compact)
    email_status_key = f"_email_sent_{norm_sid}"
    if email_status_key in st.session_state and st.session_state[email_status_key]:
        email_timestamp = st.session_state.get(f"{email_status_key}_time", "recently")
        st.caption(f"✅ Email sent to student {email_timestamp}")
    
    st.divider()

    # ---------- Eligibility map (skip hidden) - with caching ----------
    eligibility_cache_key = f"_eligibility_cache_{norm_sid}"
    student_data_hash_key = f"_student_data_hash_{norm_sid}"
    
    # Create a hash of student data to detect changes
    student_data_str = f"{norm_sid}_{str(student_row.to_dict())}"
    current_hash = hashlib.md5(student_data_str.encode()).hexdigest()
    cached_hash = st.session_state.get(student_data_hash_key)
    
    # Use cached eligibility if student data hasn't changed
    if (eligibility_cache_key in st.session_state and 
        cached_hash == current_hash and 
        st.session_state.get(eligibility_cache_key)):
        status_dict, justification_dict = st.session_state[eligibility_cache_key]
    else:
        # Calculate eligibility for all courses
        status_dict: Dict[str, str] = {}
        justification_dict: Dict[str, str] = {}
        # Include both advised AND optional courses for concurrent/corequisite checks
        # Guard against None values from legacy sessions
        advised_list = slot.get("advised") or []
        optional_for_checks = slot.get("optional") or []
        current_advised_for_checks = list(advised_list) + list(optional_for_checks)
        
        # Compute mutual concurrent/corequisite pairs once for the courses table (CACHED)
        mutual_pairs = get_mutual_pairs_cached(st.session_state.courses_df)
        
        for course_code in st.session_state.courses_df["Course Code"]:
            code = str(course_code)
            if code in hidden_for_student:
                continue
            status, justification = check_eligibility(
                student_row, code, current_advised_for_checks, st.session_state.courses_df, 
                registered_courses=[], mutual_pairs=mutual_pairs, bypass_map=student_bypasses
            )
            status_dict[code] = status
            justification_dict[code] = justification
        
        # Cache the results
        st.session_state[eligibility_cache_key] = (status_dict, justification_dict)
        st.session_state[student_data_hash_key] = current_hash

    # ---------- Build display rows (screen Action shows Advised / Optional / Advised-Repeat) ----------
    rows = []
    for _, info in st.session_state.courses_df.iterrows():
        code = str(info["Course Code"])
        if code in hidden_for_student:
            continue
        if code in (slot.get("repeat", []) or []):
            action = "Advised-Repeat"
        elif code in (slot.get("advised", []) or []):
            action = "Advised"
        elif code in (slot.get("optional", []) or []):
            action = "Optional"
        else:
            action = ""
        rows.append(
            {
                "Course Code": code,
                "Type": info.get("Type", ""),
                "Requisites": build_requisites_str(info),
                "Eligibility Status": status_dict.get(code, ""),
                "Justification": justification_dict.get(code, ""),
                "Offered": str(info.get("Offered", "")).strip().lower() == "yes",
                "Action": action,
            }
        )

    display_df = pd.DataFrame(rows)
    req_df = display_df[display_df["Type"].astype(str).str.lower() == "required"].copy()
    int_df = display_df[display_df["Type"].astype(str).str.lower() == "intensive"].copy()

    st.markdown("### Course Eligibility")
    if not req_df.empty:
        st.markdown("**Required Courses**")
        st.dataframe(style_df(req_df), width=1200)
    if not int_df.empty:
        st.markdown("**Intensive Courses**")
        st.dataframe(style_df(int_df), width=1200)

    # ---------- Selection options (eligible + offered, not hidden/completed/registered) ----------
    offered_yes = {
        str(c) for c in st.session_state.courses_df.loc[
            st.session_state.courses_df["Offered"].astype(str).str.lower() == "yes",
            "Course Code",
        ].tolist()
    }

    def _eligible_options() -> List[str]:
        opts: List[str] = []
        for c in map(str, st.session_state.courses_df["Course Code"].tolist()):
            if c in hidden_for_student:
                continue
            if c not in offered_yes:
                continue
            if check_course_completed(student_row, c) or check_course_registered(student_row, c):
                continue
            status = status_dict.get(c, "")
            if status in ("Eligible", "Eligible (Bypass)"):
                opts.append(c)
        return sorted(opts)

    eligible_opts = _eligible_options()
    optset = set(eligible_opts)

    # Options for repeat: completed or registered courses
    def _repeat_options() -> List[str]:
        opts: List[str] = []
        for c in map(str, st.session_state.courses_df["Course Code"].tolist()):
            if c in hidden_for_student:
                continue
            if check_course_completed(student_row, c) or check_course_registered(student_row, c):
                opts.append(c)
        return sorted(opts)
    
    repeat_opts = _repeat_options()

    default_advised = [c for c in (slot.get("advised", []) or []) if c in optset]
    default_repeat = [c for c in (slot.get("repeat", []) or []) if c in repeat_opts]
    default_optional = [c for c in (slot.get("optional", []) or []) if c in optset]

    # ---------- Save form (explicit autosave for *this* student) ----------
    st.markdown("---")
    st.markdown("### Advising Recommendations")
    
    def _persist_student_selections(
        advised_selection: List[str],
        repeat_selection: List[str],
        optional_selection: List[str],
        note_value: str,
    ) -> None:
        # Enforce mutual exclusivity: remove any courses from optional that are in advised
        advised_set = set(advised_selection)
        clean_optional = [c for c in optional_selection if c not in advised_set]
        
        selection_data = {
            "advised": list(advised_selection),
            "repeat": list(repeat_selection),
            "optional": clean_optional,
            "note": note_value,
        }
        
        # Update both the global session state and the major bucket
        st.session_state.advising_selections[norm_sid] = selection_data
        
        # Also update the bucket to ensure persistence across reruns
        major = st.session_state.get("current_major", "")
        if major and major in st.session_state.majors:
            st.session_state.majors[major]["advising_selections"][norm_sid] = selection_data

    def _build_student_download_bytes(
        advised_selection: List[str],
        repeat_selection: List[str],
        optional_selection: List[str],
        note_value: str,
    ) -> bytes:
        export_df = display_df.copy()
        for col in ("Type", "Requisites"):
            if col in export_df.columns:
                export_df.drop(columns=[col], inplace=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Advising")

        current_period = get_current_period()
        period_info = (
            f"Advising Period: {current_period.get('semester', '')} {current_period.get('year', '')} — "
            f"Advisor: {current_period.get('advisor_name', '')}"
        )

        apply_excel_formatting(
            output=output,
            student_name=str(student_row["NAME"]),
            student_id=norm_sid,
            credits_completed=int(cr_comp),
            standing=standing,
            note=note_value,
            advised_credits=_sum_credits(advised_selection),
            optional_credits=_sum_credits(optional_selection),
            period_info=period_info,
        )

        output.seek(0)
        return output.getvalue()

    # Remove mutual exclusivity - advised courses shouldn't appear in optional options
    # We handle this dynamically: options for optional exclude current advised, and vice versa
    # Get current selections from session state (for real-time mutual exclusivity)
    current_advised_sel = set(st.session_state.get(advised_key, default_advised))
    current_optional_sel = set(st.session_state.get(optional_key, default_optional))
    
    # Filter options: optional can't include advised, advised can't include optional
    optional_opts = [c for c in eligible_opts if c not in current_advised_sel]
    advised_opts_filtered = [c for c in eligible_opts if c not in current_optional_sel]
    
    # Pagination for large course lists
    if "_show_all_courses" not in st.session_state:
        st.session_state._show_all_courses = False
    
    def _paginate_courses(courses_list: List[str], page_size: int = 25) -> Tuple[List[str], int]:
        """Paginate course list. Returns (paginated_list, num_pages)"""
        total = len(courses_list)
        num_pages = max(1, (total + page_size - 1) // page_size)
        
        if st.session_state._show_all_courses:
            return courses_list, num_pages
        else:
            return courses_list[:page_size], num_pages
    
    advised_opts_paginated, advised_pages = _paginate_courses(advised_opts_filtered)
    optional_opts_paginated, optional_pages = _paginate_courses(optional_opts)
    
    with st.form(key=f"advise_form_{norm_sid}"):
        advised_selection = st.multiselect(
            "Advised Courses (Eligible, Not Yet Taken)", 
            options=advised_opts_paginated, 
            default=[c for c in default_advised if c in advised_opts_paginated], 
            key=advised_key,
            help="Primary course recommendations for this student. Shows course title and credits.",
            format_func=lambda x: _format_course_option(x, st.session_state.courses_df)
        )
        
        if advised_pages > 1 and not st.session_state._show_all_courses:
            st.caption(f"Showing 1 of {advised_pages} pages")
        
        optional_selection = st.multiselect(
            "Optional Courses",
            options=optional_opts_paginated,
            default=[c for c in default_optional if c in optional_opts_paginated],
            key=optional_key,
            help="Additional optional courses (cannot overlap with Advised). Shows course title and credits.",
            format_func=lambda x: _format_course_option(x, st.session_state.courses_df)
        )
        
        if optional_pages > 1 and not st.session_state._show_all_courses:
            st.caption(f"Showing 1 of {optional_pages} pages")
        repeat_selection = st.multiselect(
            "Repeat Courses (Completed or Registered)", 
            options=repeat_opts, 
            default=default_repeat, 
            key=repeat_key,
            help="📝 Courses to repeat to improve GPA. These count toward semester load but student has already completed them.",
            format_func=lambda x: _format_course_option(x, st.session_state.courses_df)
        )
        if repeat_opts:
            st.caption("💡 **Tip**: Repeating courses replaces prior grades in GPA calculation.")
        
        note_input = st.text_area(
            "Advisor Note (optional)", value=slot.get("note", ""), key=note_key
        )

        # Four buttons: Save, Email, Recommend, and Show All Courses
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([1.3, 1.3, 1.2, 1.2])

        with btn_col1:
            submitted = st.form_submit_button("💾 Save Selections", use_container_width=True, type="primary")

        with btn_col2:
            email_clicked = st.form_submit_button("✉️ Email Student", use_container_width=True)
        
        with btn_col3:
            recommend_clicked = st.form_submit_button("🎯 Recommend", use_container_width=True, type="secondary", help="Auto-recommend next courses")
        
        with btn_col4:
            if not st.session_state._show_all_courses and (advised_pages > 1 or optional_pages > 1):
                show_all_clicked = st.form_submit_button("📋 Show All", use_container_width=True, type="secondary")
                if show_all_clicked:
                    st.session_state._show_all_courses = True
                    st.rerun()

        if submitted or email_clicked or recommend_clicked:
            if recommend_clicked:
                # Get recommendations
                current_selected = advised_selection + optional_selection
                recommendations = _get_recommended_courses(
                    eligible_opts, 
                    current_selected,
                    st.session_state.courses_df,
                    max_recommendations=3
                )
                
                if recommendations:
                    st.info(f"🎯 **Recommended Courses**: {', '.join(recommendations)}\n\nClick 'Show All' to see all options, or add these to your selections above.")
                else:
                    st.info("✓ All available courses have been selected!")
            else:
                _persist_student_selections(advised_selection, repeat_selection, optional_selection, note_input)

            if submitted:
                # Show saving status with better feedback
                status_placeholder = st.empty()
                
                try:
                    # Show saving message
                    with status_placeholder.container():
                        st.info("⏳ Saving to Google Drive...")
                    
                    # Perform save operation
                    session_id = save_session_for_student(norm_sid)
                    
                    time.sleep(0.5)
                    
                    # Show success message
                    if session_id:
                        with status_placeholder.container():
                            st.success("✅ Saved successfully! Changes have been synced to Google Drive.")
                    else:
                        with status_placeholder.container():
                            st.warning("⚠️ Save completed with warnings. Check logs for details.")
                    
                    # Mark as autoloaded so we don't reload from Drive and overwrite
                    st.session_state[f"_autoloaded_{norm_sid}"] = True
                    
                    time.sleep(1.5)
                    status_placeholder.empty()
                    st.rerun()
                    
                except Exception as e:
                    with status_placeholder.container():
                        st.error(f"❌ Error saving: {str(e)}")

            elif email_clicked:
                # Email student with template
                from email_manager import get_student_email, send_advising_email

                student_email = get_student_email(str(norm_sid))
                if not student_email:
                    show_notification(
                        f"No email found for student {norm_sid}. Upload email roster first.",
                        "error",
                        persistent=True
                    )
                    st.rerun()
                else:
                    # Get period info for email
                    current_period = get_current_period()
                    period_info = f"{current_period.get('semester', '')} {current_period.get('year', '')} — Advisor: {current_period.get('advisor_name', '')}"
                    
                    # Get advisor email if available
                    advisor_email = st.session_state.get("advisor_email", "")
                    
                    success, message = send_advising_email(
                        to_email=student_email,
                        student_name=str(student_row["NAME"]),
                        student_id=str(norm_sid),
                        advised_courses=list(advised_selection),
                        repeat_courses=list(repeat_selection),
                        optional_courses=list(optional_selection),
                        note=note_input,
                        courses_df=st.session_state.courses_df,
                        remaining_credits=int(cr_remaining),
                        period_info=period_info,
                        advisor_email=advisor_email if advisor_email else None,
                        cc_advisor=True,
                    )

                    if success:
                        show_action_feedback("email", True, f"Sent to {student_email}")
                        log_info(f"Advising email sent to {student_email} for student {norm_sid}")
                        # Track email sent in session state
                        from datetime import datetime
                        st.session_state[f"_email_sent_{norm_sid}"] = True
                        st.session_state[f"_email_sent_{norm_sid}_time"] = datetime.now().strftime("%I:%M %p")
                    else:
                        show_action_feedback("email", False, message)
                    st.rerun()

    # ---------- Download Report ----------
    current_advised = slot.get("advised", []) or []
    current_repeat = slot.get("repeat", []) or []
    current_optional = slot.get("optional", []) or []
    current_note = slot.get("note", "")
    
    st.download_button(
        "📥 Download Current Advising Report",
        data=_build_student_download_bytes(
            current_advised,
            current_repeat,
            current_optional,
            current_note,
        ),
        file_name=f"Advising_{norm_sid}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="secondary",
        use_container_width=True,
        key=f"download_advising_{norm_sid}",
    )

    # ---------- Requisite Bypass Manager ----------
    with st.expander("🔓 Requisite Bypasses", expanded=len(student_bypasses) > 0):
        st.markdown("Grant a bypass to allow a student to register for a course without meeting prerequisites.")
        
        # Get courses that are "Not Eligible" (excluding hidden/completed/registered)
        not_eligible_courses = [
            code for code, status in status_dict.items()
            if status == "Not Eligible" and code not in hidden_for_student
        ]
        
        # Show existing bypasses
        if student_bypasses:
            st.markdown("**Active Bypasses:**")
            for course_code, bypass_info in list(student_bypasses.items()):
                col1, col2, col3 = st.columns([3, 5, 2])
                with col1:
                    st.markdown(f"**{course_code}**")
                with col2:
                    bypass_note = bypass_info.get("note", "")
                    bypass_advisor = bypass_info.get("advisor", "")
                    display_text = f"By {bypass_advisor}" if bypass_advisor else ""
                    if bypass_note:
                        display_text += f": {bypass_note}" if display_text else bypass_note
                    st.caption(display_text or "No note")
                with col3:
                    if st.button("Remove", key=f"remove_bypass_{norm_sid}_{course_code}", type="secondary"):
                        del student_bypasses[course_code]
                        st.session_state[bypasses_key][norm_sid] = student_bypasses
                        save_session_for_student(norm_sid)
                        show_action_feedback("save", True, f"Bypass removed for {course_code}")
                        st.rerun()
            st.markdown("---")
        
        # Add new bypass
        if not_eligible_courses:
            st.markdown("**Grant New Bypass:**")
            bypass_course = st.selectbox(
                "Course to bypass",
                options=not_eligible_courses,
                key=f"bypass_course_{norm_sid}",
                help="Select a course that is currently 'Not Eligible'"
            )
            
            # Show why it's not eligible
            if bypass_course:
                reason = justification_dict.get(bypass_course, "")
                if reason:
                    st.caption(f"Currently not eligible: {reason}")
            
            bypass_note = st.text_input(
                "Bypass reason (optional)",
                key=f"bypass_note_{norm_sid}",
                placeholder="e.g., Department chair approved, Transfer credit pending"
            )
            
            current_period = get_current_period()
            advisor_name = current_period.get("advisor_name", "")
            
            if st.button("Grant Bypass", key=f"grant_bypass_{norm_sid}", type="primary"):
                from datetime import datetime
                student_bypasses[bypass_course] = {
                    "note": bypass_note,
                    "advisor": advisor_name,
                    "timestamp": datetime.now().isoformat()
                }
                st.session_state[bypasses_key][norm_sid] = student_bypasses
                save_session_for_student(norm_sid)
                show_action_feedback("save", True, f"Bypass granted for {bypass_course}")
                st.rerun()
        else:
            if not student_bypasses:
                st.info("No courses currently need a bypass. All courses are either eligible, completed, or registered.")

    # ---------- Hidden courses manager ----------
    with st.expander("🚫 Manage Hidden Courses"):
        all_codes = sorted(map(str, st.session_state.courses_df["Course Code"].tolist()))
        def_hidden = [c for c in all_codes if c in hidden_for_student]
        new_hidden = st.multiselect(
            "Remove (hide) these courses",
            options=all_codes,
            default=def_hidden,
            key=f"hidden_ms_{norm_sid}",
            help="Hidden courses don't appear in tables or selection lists; persisted per student.",
        )
        if st.button("Save Hidden Courses", key=f"save_hidden_{norm_sid}"):
            set_for_student(norm_sid, new_hidden)
            show_action_feedback("save", True, "Hidden courses updated")
            st.rerun()
