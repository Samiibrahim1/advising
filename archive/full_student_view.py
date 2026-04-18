# full_student_view.py

import streamlit as st
import pandas as pd
from io import BytesIO
from typing import List, Dict, Any, Tuple, Optional, Union
from advising_utils import (
    check_course_completed,
    check_course_registered,
    check_eligibility,
    get_student_standing,
    build_requisites_str,
    get_corequisite_and_concurrent_courses,
    get_mutual_concurrent_pairs,
    get_mutual_pairs_cached,
    get_coreq_concurrent_cached,
    style_df,  # kept (used elsewhere in app)
    log_info,
    log_error,
    get_student_selections,
    get_student_bypasses,
)
from reporting import (
    add_summary_sheet,
    apply_full_report_formatting,
    apply_individual_compact_formatting,
)
from advising_history import load_all_sessions_for_period


def _get_drive_module():
    """Lazy loader for google_drive module to avoid import-time side effects."""
    import google_drive as gd

    return gd


# -----------------------------
# Color map (aligned with Advising table)
# -----------------------------
_CODE_COLORS = {
    "c": "#C6E0B4",  # Completed -> light green
    "r": "#BDD7EE",  # Registered -> light blue
    "s": "#D9E1F2",  # Simulated (will register) -> light purple/blue
    "a": "#FFF2CC",  # Advised -> light yellow
    "ar": "#FFD966",  # Advised-Repeat -> darker yellow/orange
    "o": "#FFE699",  # Optional -> light orange
    "na": "#E1F0FF",  # Eligible not chosen -> light blue-tint
    "ne": "#F8CECC",  # Not Eligible -> light red
    "b": "#D5A6E6",  # Bypass -> light purple
}


def _style_codes(
    df: pd.DataFrame, code_cols: List[str]
) -> "pd.io.formats.style.Styler":
    """
    Return a Styler that colors the code columns based on _CODE_COLORS.
    Works for both All Students (many rows) and Individual Student (one row).
    """

    def _bg(v):
        col = _CODE_COLORS.get(str(v).strip().lower())
        return f"background-color: {col}" if col else ""

    styler = df.style
    if code_cols:
        styler = styler.map(_bg, subset=code_cols)
    return styler


def _get_semester_structure(courses_df):
    """Parse semester structure from courses table.

    Expects a 'Suggested Semester' column with format: 'Fall-1', 'Spring-2', 'Summer-3', etc.
    Returns dict mapping semester keys to list of course info dicts.
    """
    semester_col = None
    for col in courses_df.columns:
        if "suggested" in col.lower() and "semester" in col.lower():
            semester_col = col
            break

    if not semester_col:
        return {}

    semesters = {}

    for _, course_row in courses_df.iterrows():
        semester_value = str(course_row.get(semester_col, "")).strip()

        if not semester_value or pd.isna(semester_value) or semester_value == "nan":
            continue

        # Parse format like "Fall-1", "Spring-2", "Summer-3"
        if "-" in semester_value:
            parts = semester_value.split("-")
            if len(parts) == 2:
                semester_name = parts[0].strip()
                year_num = parts[1].strip()

                semester_key = f"{semester_name}-{year_num}"

                if semester_key not in semesters:
                    semesters[semester_key] = []

                semesters[semester_key].append(
                    {
                        "code": course_row["Course Code"],
                        "title": course_row.get(
                            "Course Title", course_row.get("Title", "")
                        ),
                        "credits": course_row.get("Credits", 3),
                        "semester": semester_name,
                        "year": year_num,
                    }
                )

    return semesters


def render_degree_plan_table(courses_df, progress_df):
    """Render degree plan view for all students."""
    st.markdown("### 🎓 Degree Plan View - All Students")
    st.caption(
        "Shows student progress organized by the curriculum's suggested semester structure"
    )

    # Get semester structure
    semesters = _get_semester_structure(courses_df)

    if not semesters:
        st.warning(
            "⚠️ No 'Suggested Semester' column found in courses table. Please add a column with format like 'Fall-1', 'Spring-2', etc."
        )
        return None

    # Build ordered list of courses by semester
    semester_order = sorted(
        semesters.keys(),
        key=lambda x: (
            int(x.split("-")[1]),
            {"fall": 0, "spring": 1, "summer": 2}.get(x.split("-")[0].lower(), 99),
        ),
    )
    all_courses = []
    for sem_key in semester_order:
        all_courses.extend([c["code"] for c in semesters[sem_key]])

    # Get bypasses for this major
    major = st.session_state.get("current_major", "")

    # Use cached values
    cached = _get_fsv_cache(major)
    mutual_pairs = cached["mutual_pairs"]

    bypasses_key = f"bypasses_{major}"
    all_bypasses = st.session_state.get(bypasses_key, {})

    # Pre-fetch all student selections once (PERFORMANCE: avoid repeated lookups)
    all_selections = {}
    for sid in progress_df["ID"].tolist():
        all_selections[sid] = get_student_selections(sid)
        all_selections[str(sid)] = all_selections[sid]  # Handle both int and str keys

    # Build table
    table_data = []
    for _, student in progress_df.iterrows():
        student_id = student.get("ID", "")

        # Get bypasses and selections for this student (cached lookup)
        student_bypasses = (
            all_bypasses.get(student_id) or all_bypasses.get(str(student_id)) or {}
        )
        slot = all_selections.get(student_id) or all_selections.get(str(student_id)) or {}
        advised = set(slot.get("advised", []))
        repeat = set(slot.get("repeat", []))
        optional = set(slot.get("optional", []))

        row = {
            "NAME": student.get("NAME", ""),
            "ID": student_id,
            "Total Credits Completed": student.get("Total Credits Completed", 0),
            "Remaining Credits": student.get("Remaining Credits", 0),
            "Standing": student.get("Standing", ""),
        }

        # Add course statuses
        for course_code in all_courses:
            status_val = student.get(course_code, "")

            if pd.isna(status_val) or status_val == "":
                if course_code in advised or course_code in optional:
                    row[course_code] = "a"
                elif course_code in repeat:
                    row[course_code] = "ar"
                else:
                    # Check eligibility
                    is_eligible_status, _ = check_eligibility(
                        student,
                        course_code,
                        [],
                        courses_df,
                        ignore_offered=True,
                        mutual_pairs=mutual_pairs,
                        bypass_map=student_bypasses,
                    )
                    # Map check_eligibility status to display codes
                    status_map = {
                        "Completed": "c",
                        "Registered": "r",
                        "Eligible": "na",
                        "Eligible (Bypass)": "b",
                        "Not Eligible": "ne",
                    }
                    row[course_code] = status_map.get(is_eligible_status, "ne")
            else:
                status_str = str(status_val).strip().lower()
                # Even if they have a status in the sheet, check if it's overridden by advising
                if course_code in advised or course_code in optional:
                    row[course_code] = "a"
                elif course_code in repeat:
                    row[course_code] = "ar"
                else:
                    row[course_code] = status_str

        table_data.append(row)

    table_df = pd.DataFrame(table_data)

    # Display legend
    legend_md = """
    **Legend**: `c` = Completed | `r` = Registered | `s` = Simulated | `a` = Advised | `ar` = Advised Repeat | 
    `o` = Optional | `na` = Eligible | `b` = Bypass | `ne` = Not Eligible | `f` = Failed
    """

    st.write(legend_md)

    # Display table with styling
    display_df = table_df.set_index("NAME")
    display_df.index.name = "Student"

    styled = _style_codes(display_df, all_courses)
    st.dataframe(styled, width=1200, height=600)

    # Show semester headers as info
    with st.expander("📅 Semester Structure"):
        for sem_key in semester_order:
            courses_in_sem = [c["code"] for c in semesters[sem_key]]
            total_credits = sum(c["credits"] for c in semesters[sem_key])
            st.markdown(
                f"**{sem_key}** ({total_credits} cr): {', '.join(courses_in_sem)}"
            )

    return table_df


def full_student_view():
    """
    Two modes:
      - All Students (wide table with compact status codes)
      - Individual Student (subset + export)
    """
    if "courses_df" not in st.session_state or st.session_state.courses_df.empty:
        st.warning("Courses table not loaded.")
        return
    if "progress_df" not in st.session_state or st.session_state.progress_df.empty:
        st.warning("Progress report not loaded.")
        return
    if "advising_selections" not in st.session_state:
        st.session_state.advising_selections = {}

    major = st.session_state.get("current_major", "")
    from advising_period import get_current_period

    current_period = get_current_period()
    period_id = current_period.get("period_id", "")
    sessions_loaded_key = f"_sessions_loaded_{major}_{period_id}"
    
    # Check if sessions need to be loaded
    # Also reload if advising_selections is empty but we think sessions were loaded
    needs_load = sessions_loaded_key not in st.session_state
    if not needs_load and not st.session_state.get("advising_selections"):
        # Flag is set but no selections - force reload
        needs_load = True
        log_info("Sessions flag set but no selections - forcing reload")
    
    if needs_load:
        with st.spinner("Loading advising sessions..."):
            load_all_sessions_for_period()
        st.session_state[sessions_loaded_key] = True

    tab = st.tabs(
        ["All Students", "Individual Student", "QAA Sheet", "Schedule Conflict"]
    )
    with tab[0]:
        _render_all_students()
    with tab[1]:
        _render_individual_student()
    with tab[2]:
        _render_qaa_sheet()
    with tab[3]:
        _render_schedule_conflict()


def _get_fsv_cache(major: str = None) -> dict:
    """Get or create the Full Student View cache for the specified major."""
    if major is None:
        major = st.session_state.get("current_major", "")

    cache_key = f"_fsv_cache_{major}"

    if cache_key not in st.session_state or st.session_state.get(
        f"{cache_key}_stale", False
    ):
        courses_df = st.session_state.courses_df
        # Use cached versions for better performance
        st.session_state[cache_key] = {
            "coreq_concurrent_courses": get_coreq_concurrent_cached(courses_df),
            "mutual_pairs": get_mutual_pairs_cached(courses_df),
        }
        st.session_state[f"{cache_key}_stale"] = False

    return st.session_state[cache_key]


def _render_all_students():
    if "simulated_courses" not in st.session_state:
        st.session_state.simulated_courses = []

    # Get or create cache for expensive calculations
    major = st.session_state.get("current_major", "")
    cached = _get_fsv_cache(major)

    # Legacy support for old cache key
    if "coreq_concurrent_courses" not in st.session_state:
        st.session_state.coreq_concurrent_courses = cached["coreq_concurrent_courses"]

    st.markdown("### 🎯 Course Offering Simulation")
    st.caption(
        "Select co-requisite or concurrent courses you plan to offer. The table will show eligibility assuming eligible students register for these courses."
    )

    with st.form("simulation_form"):
        col_select, col_actions = st.columns([3, 1])

        with col_select:
            # Only show co-requisite and concurrent courses for simulation
            available_courses = st.session_state.coreq_concurrent_courses

            if not available_courses:
                st.info(
                    "ℹ️ No co-requisite or concurrent courses found in the courses table. Simulation only supports courses that are required alongside other courses."
                )

            selected_sim_courses = st.multiselect(
                "Select co-requisite/concurrent courses to simulate",
                options=available_courses,
                default=[
                    c
                    for c in st.session_state.simulated_courses
                    if c in available_courses
                ],
                help="Only co-requisite and concurrent courses are shown since prerequisite courses would already be completed.",
            )

        with col_actions:
            st.write("")
            st.write("")
            col_apply, col_clear = st.columns(2)
            with col_apply:
                apply_clicked = st.form_submit_button(
                    "✅ Apply", type="primary", use_container_width=True
                )
            with col_clear:
                clear_clicked = st.form_submit_button("🔄 Clear", use_container_width=True)

        if apply_clicked:
            st.session_state.simulated_courses = selected_sim_courses
            st.rerun()
        if clear_clicked:
            st.session_state.simulated_courses = []
            st.rerun()

    if st.session_state.simulated_courses:
        st.info(
            f"🎬 **Simulation Active:** {len(st.session_state.simulated_courses)} course(s) selected - {', '.join(st.session_state.simulated_courses[:5])}{' ...' if len(st.session_state.simulated_courses) > 5 else ''}"
        )

    st.markdown("---")

    df = st.session_state.progress_df.copy()
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    df = df.dropna(subset=["ID"])
    df["ID"] = df["ID"].astype(int)

    progress_df_original = df.copy().set_index("ID")
    original_rows = {int(idx): row for idx, row in progress_df_original.iterrows()}

    # Get courses_df from session state first
    courses_df = st.session_state.courses_df

    # Compute derived columns
    df["Total Credits Completed"] = (
        pd.to_numeric(df.get("# of Credits Completed", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
        + pd.to_numeric(df.get("# Registered", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
    ).astype(int)
    df["Standing"] = df["Total Credits Completed"].apply(get_student_standing)

    def _get_advising_status(sid):
        slot = get_student_selections(sid)
        # Mark as "Advised" if any advising activity exists (courses selected OR note added)
        has_advised = bool(slot.get("advised"))
        has_optional = bool(slot.get("optional"))
        has_repeat = bool(slot.get("repeat"))
        has_note = bool(slot.get("note", "").strip())
        return (
            "Advised"
            if (has_advised or has_optional or has_repeat or has_note)
            else "Not Advised"
        )

    df["Advising Status"] = df["ID"].apply(_get_advising_status)

    # Normalize remaining credits for filtering and display
    remaining_credits_series = (
        pd.to_numeric(df.get("# Remaining", 0), errors="coerce").fillna(0).astype(int)
    )
    df["Remaining Credits"] = remaining_credits_series
    min_remaining = (
        int(remaining_credits_series.min()) if not remaining_credits_series.empty else 0
    )
    max_remaining = (
        int(remaining_credits_series.max()) if not remaining_credits_series.empty else 0
    )

    if min_remaining == max_remaining:
        remaining_range = (min_remaining, max_remaining)
        st.caption(f"All students currently have {min_remaining} remaining credits.")
    else:
        remaining_range = st.slider(
            "Filter by remaining credits",
            min_value=min_remaining,
            max_value=max_remaining,
            value=(min_remaining, max_remaining),
            help="Narrow the table to students within the selected remaining-credit range.",
        )

    if min_remaining != max_remaining:
        df = df[
            (df["Remaining Credits"] >= remaining_range[0])
            & (df["Remaining Credits"] <= remaining_range[1])
        ]

    type_series = courses_df.get("Type", pd.Series(dtype=str))

    # Build semester filter options
    if "Suggested Semester" in courses_df.columns:
        all_semesters = courses_df["Suggested Semester"].dropna().unique().tolist()
        all_semesters = [
            str(s).strip()
            for s in all_semesters
            if str(s).strip() and str(s).lower() not in ["nan", "none"]
        ]

        # Extract unique semester types (Fall, Spring, Summer)
        semester_types = set()
        for sem in all_semesters:
            parts = sem.split("-")
            if len(parts) == 2:
                semester_types.add(parts[0])

        # Build filter options
        filter_options = ["All Courses"]
        filter_options.extend(sorted(semester_types))  # All Fall, All Spring, etc.
        filter_options.extend(sorted(all_semesters))  # Fall-1, Spring-2, etc.

        semester_filter = st.selectbox(
            "📅 Filter by Semester",
            options=filter_options,
            help="Show all courses or filter by specific semester (Fall-1, Spring-2) or semester type (Fall, Spring, Summer)",
        )
    else:
        semester_filter = "All Courses"

    required_courses = (
        courses_df.loc[
            type_series.astype(str).str.strip().str.lower() == "required",
            "Course Code",
        ]
        .dropna()
        .tolist()
    )
    intensive_courses = (
        courses_df.loc[
            type_series.astype(str).str.strip().str.lower() == "intensive",
            "Course Code",
        ]
        .dropna()
        .tolist()
    )

    # Filter courses by semester if a filter is active
    def filter_courses_by_semester(course_list, semester_filter_val):
        if (
            semester_filter_val == "All Courses"
            or "Suggested Semester" not in courses_df.columns
        ):
            return course_list

        filtered = []
        for course in course_list:
            course_info = courses_df.loc[courses_df["Course Code"] == course]
            if not course_info.empty:
                suggested_sem = str(
                    course_info.iloc[0].get("Suggested Semester", "")
                ).strip()
                if not suggested_sem or suggested_sem.lower() in ["nan", "none"]:
                    continue

                # Check if matches: exact match for specific semesters or semester type prefix
                if (
                    suggested_sem == semester_filter_val
                ):  # Exact match (e.g., "Fall-1" == "Fall-1")
                    filtered.append(course)
                elif "-" not in semester_filter_val and suggested_sem.startswith(
                    semester_filter_val + "-"
                ):
                    # Semester type filter (e.g., "Fall" matches "Fall-1", "Fall-2", etc.)
                    filtered.append(course)
        return filtered

    if semester_filter != "All Courses":
        required_courses = filter_courses_by_semester(required_courses, semester_filter)
        intensive_courses = filter_courses_by_semester(
            intensive_courses, semester_filter
        )

    base_display_cols = [
        "NAME",
        "ID",
        "Total Credits Completed",
        "Remaining Credits",
        "Standing",
        "Advising Status",
    ]
    legend_md = "*Legend:* c=Completed, r=Registered, s=Simulated (will register), a=Advised, ar=Advised-Repeat, o=Optional, na=Eligible not chosen, ne=Not Eligible"

    simulated_courses = st.session_state.simulated_courses
    simulated_completions = {}

    # Use cached mutual pairs (already computed above)
    mutual_pairs = cached["mutual_pairs"]

    # Get bypasses for this major
    major = st.session_state.get("current_major", "")
    bypasses_key = f"bypasses_{major}"
    all_bypasses = st.session_state.get(bypasses_key, {})

    if simulated_courses:
        with st.spinner("Calculating simulation results..."):
            for sid in df["ID"].astype(int).tolist():
                row_original = original_rows.get(int(sid))
                if row_original is None:
                    continue

                # Get bypasses for this student
                student_bypasses = all_bypasses.get(sid) or all_bypasses.get(str(sid)) or {}

                simulated_completions[sid] = []
                advised_list = (
                    st.session_state.advising_selections.get(int(sid), {}).get(
                        "advised", []
                    )
                    or []
                )

                max_iterations = len(simulated_courses)
                for iteration in range(max_iterations):
                    added_this_iteration = False
                    for sim_course in simulated_courses:
                        if sim_course in simulated_completions[sid]:
                            continue

                        stt, _ = check_eligibility(
                            row_original,
                            sim_course,
                            advised_list,
                            st.session_state.courses_df,
                            registered_courses=simulated_completions[sid],
                            ignore_offered=True,
                            mutual_pairs=mutual_pairs,
                            bypass_map=student_bypasses,
                        )
                        if stt in ("Eligible", "Eligible (Bypass)"):
                            simulated_completions[sid].append(sim_course)
                            added_this_iteration = True

                    if not added_this_iteration:
                        break

    def status_code(
        row_original: pd.Series,
        student_id: int,
        course: str,
        simulated_for_student: list,
        _student_selections_cache: dict = None,
        _student_bypasses_cache: dict = None,
    ) -> str:
        # Use cached values if provided (PERFORMANCE: avoid repeated lookups)
        if _student_selections_cache and student_id in _student_selections_cache:
            sel = _student_selections_cache[student_id]
        else:
            sel = get_student_selections(student_id)
        
        advised_list = sel.get("advised", []) or []
        optional_list = sel.get("optional", []) or []
        repeat_list = sel.get("repeat", []) or []

        # Use cached bypasses if provided
        if _student_bypasses_cache and student_id in _student_bypasses_cache:
            student_bypasses = _student_bypasses_cache[student_id]
        else:
            student_bypasses = get_student_bypasses(student_id, major)

        if course in repeat_list:
            return "ar"
        if check_course_completed(row_original, course):
            return "c"
        if check_course_registered(row_original, course):
            return "r"
        if course in simulated_for_student:
            return "s"
        if course in optional_list:
            return "o"
        if course in advised_list:
            return "a"

        stt, _ = check_eligibility(
            row_original,
            course,
            advised_list,
            st.session_state.courses_df,
            registered_courses=simulated_for_student,
            ignore_offered=True,
            mutual_pairs=mutual_pairs,
            bypass_map=student_bypasses,
        )
        if stt == "Eligible (Bypass)":
            return "b"
        return "na" if stt == "Eligible" else "ne"

    # Pre-fetch all student selections and bypasses once (PERFORMANCE)
    all_student_selections = {}
    all_student_bypasses = {}
    for sid in df["ID"].astype(int).tolist():
        all_student_selections[sid] = get_student_selections(sid)
        all_student_bypasses[sid] = all_bypasses.get(sid) or all_bypasses.get(str(sid)) or {}

    def render_course_table(label: str, course_codes: List[str], key_suffix: str):
        if not course_codes:
            st.info(f"No {label.lower()} courses available.")
            return None, []

        # Use session state to store confirmed selections - make major-specific
        major = st.session_state.get("current_major", "DEFAULT")
        confirmed_key = f"confirmed_{key_suffix}_courses_{major}"
        if confirmed_key not in st.session_state:
            st.session_state[confirmed_key] = course_codes

        # Ensure confirmed selections are valid for current course_codes
        valid_confirmed = [
            c for c in st.session_state[confirmed_key] if c in course_codes
        ]
        if not valid_confirmed and course_codes:
            valid_confirmed = course_codes

        with st.expander(f"Select {label.lower()} course columns", expanded=False):
            with st.form(key=f"course_selection_form_{key_suffix}"):
                temp_selected = st.multiselect(
                    f"{label} course columns",
                    options=course_codes,
                    default=valid_confirmed,
                    key=f"temp_{key_suffix}_course_columns",
                )

                col1, col2 = st.columns([1, 5])
                with col1:
                    confirm = st.form_submit_button("✓ Confirm", use_container_width=True)
                with col2:
                    st.caption("Select courses then click Confirm to update the table")

                if confirm:
                    st.session_state[confirmed_key] = temp_selected
                    st.rerun()

        selected = valid_confirmed

        if not selected:
            st.info(
                "Select at least one course column to display student eligibility statuses."
            )
            return None, []

        table_df = df[base_display_cols].copy()
        student_ids = table_df["ID"].astype(int).tolist()

        # Track statuses for summary calculation
        course_status_data = {}
        for course in selected:
            statuses = []
            for sid in student_ids:
                row_original = original_rows.get(int(sid))
                if row_original is None:
                    statuses.append("")
                    continue
                student_simulated = simulated_completions.get(sid, [])
                statuses.append(
                    status_code(
                        row_original, sid, course, student_simulated,
                        _student_selections_cache=all_student_selections,
                        _student_bypasses_cache=all_student_bypasses,
                    )
                )
            table_df[course] = statuses
            course_status_data[course] = statuses

        # Build requisites and summary data
        requisites_data = {}
        summary_data = {}
        for course in selected:
            course_info = courses_df.loc[courses_df["Course Code"] == course]
            if not course_info.empty:
                requisites_data[course] = build_requisites_str(course_info.iloc[0])
            else:
                requisites_data[course] = ""

            # Calculate summary statistics
            statuses = course_status_data[course]
            total_students = len([s for s in statuses if s])
            c_count = statuses.count("c")
            r_count = statuses.count("r")
            s_count = statuses.count("s")
            na_count = statuses.count("na")
            ne_count = statuses.count("ne")
            completion_rate = (
                f"{(c_count / total_students * 100):.0f}%"
                if total_students > 0
                else "0%"
            )
            summary_data[course] = (
                f"c:{c_count} | r:{r_count} | s:{s_count} | na:{na_count} | ne:{ne_count} | {completion_rate}"
            )

        # Show semester header if filtering
        if semester_filter != "All Courses":
            st.markdown(f"### 📅 {semester_filter}")
            st.write("")

        # Use only the student data table (no requisites/summary rows)
        display_df = table_df.set_index("NAME")
        display_df.index.name = "Student"

        # Build column config with tooltips for course columns
        column_config = {}
        for course in selected:
            req_str = requisites_data[course] if requisites_data[course] else "None"
            help_text = f"📋 {req_str}\n\n📊 {summary_data[course]}"
            column_config[course] = st.column_config.TextColumn(
                course, help=help_text, width="small"
            )

        # For export, use only student data (no requisites/summary rows)
        export_df = table_df.copy()

        st.write(legend_md)
        styled = _style_codes(display_df, selected)
        st.dataframe(styled, width=1200, height=600, column_config=column_config)
        return export_df, selected

    required_tab, intensive_tab = st.tabs(["Required Courses", "Intensive Courses"])

    required_display_df = None
    required_selected = []
    intensive_display_df = None
    intensive_selected = []

    with required_tab:
        required_display_df, required_selected = render_course_table(
            "Required", required_courses, "required"
        )

    with intensive_tab:
        intensive_display_df, intensive_selected = render_course_table(
            "Intensive", intensive_courses, "intensive"
        )

    has_required = required_display_df is not None and len(required_selected) > 0
    has_intensive = intensive_display_df is not None and len(intensive_selected) > 0

    if not has_required and not has_intensive:
        return

    if has_required or has_intensive:

        def _build_full_report_bytes() -> bytes:
            output = BytesIO()

            # Build credits lookup from courses_df
            credits_lookup = {}
            for _, course_row in courses_df.iterrows():
                code = course_row.get("Course Code", "")
                credits = course_row.get("Credits", 3)
                try:
                    credits_lookup[code] = float(credits) if pd.notna(credits) else 3.0
                except (ValueError, TypeError):
                    credits_lookup[code] = 3.0

            # Helper to calculate credits for a student
            def calc_student_credits(student_id):
                sel = (
                    st.session_state.advising_selections.get(int(student_id))
                    or st.session_state.advising_selections.get(str(int(student_id)))
                    or {}
                )
                advised_list = sel.get("advised", []) or []
                optional_list = sel.get("optional", []) or []

                # Credits Advised = sum of all advised courses (including optional)
                advised_credits = sum(credits_lookup.get(c, 3.0) for c in advised_list)
                # Optional Credits = sum of just optional courses (subset of advised)
                optional_credits = sum(
                    credits_lookup.get(c, 3.0) for c in optional_list
                )

                return advised_credits, optional_credits

            # Add credits columns to dataframes
            def add_credits_columns(df_to_modify):
                if df_to_modify is None or df_to_modify.empty:
                    return df_to_modify
                result_df = df_to_modify.copy()
                credits_advised = []
                optional_credits = []
                for _, row in result_df.iterrows():
                    sid = row.get("ID", 0)
                    adv_cr, opt_cr = calc_student_credits(sid)
                    credits_advised.append(int(adv_cr))
                    optional_credits.append(int(opt_cr))
                # Insert after Advising Status column
                adv_status_idx = (
                    result_df.columns.get_loc("Advising Status") + 1
                    if "Advising Status" in result_df.columns
                    else len(result_df.columns)
                )
                result_df.insert(adv_status_idx, "Credits Advised", credits_advised)
                result_df.insert(
                    adv_status_idx + 1, "Optional Credits", optional_credits
                )
                return result_df

            required_with_credits = (
                add_credits_columns(required_display_df) if has_required else None
            )
            intensive_with_credits = (
                add_credits_columns(intensive_display_df) if has_intensive else None
            )

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                if has_required and required_with_credits is not None:
                    required_with_credits.to_excel(
                        writer, index=False, sheet_name="Required Courses"
                    )
                if has_intensive and intensive_with_credits is not None:
                    intensive_with_credits.to_excel(
                        writer, index=False, sheet_name="Intensive Courses"
                    )

                summary_frames = []
                summary_courses: List[str] = []
                if has_required and required_with_credits is not None:
                    summary_frames.append(required_with_credits)
                    summary_courses.extend(required_selected)
                if has_intensive and intensive_with_credits is not None:
                    summary_frames.append(intensive_with_credits)
                    summary_courses.extend(intensive_selected)

                if summary_frames and summary_courses:
                    summary_input = pd.concat(summary_frames, ignore_index=True)
                    add_summary_sheet(writer, summary_input, summary_courses)

                if has_required:
                    apply_full_report_formatting(
                        writer.book,
                        sheet_name="Required Courses",
                        course_cols=required_selected,
                    )
                if has_intensive:
                    apply_full_report_formatting(
                        writer.book,
                        sheet_name="Intensive Courses",
                        course_cols=intensive_selected,
                    )

            output.seek(0)
            return output.getvalue()

        full_report_bytes = _build_full_report_bytes()
        st.download_button(
            "Download Full Advising Report",
            data=full_report_bytes,
            file_name="Full_Advising_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            help="Download Excel report with all students' course progress, advising status, and credits",
        )


def _render_individual_student():
    students_df = st.session_state.progress_df.copy()
    students_df["DISPLAY"] = (
        students_df["NAME"].astype(str) + " — " + students_df["ID"].astype(str)
    )
    choice = st.selectbox(
        "Select a student", students_df["DISPLAY"].tolist(), key="full_single_select"
    )
    sid = int(students_df.loc[students_df["DISPLAY"] == choice, "ID"].iloc[0])
    row_original = st.session_state.progress_df.loc[
        st.session_state.progress_df["ID"] == sid
    ].iloc[0]
    row = students_df.loc[students_df["ID"] == sid].iloc[0]

    # IMPORTANT: do NOT overwrite st.session_state["current_student_id"] here.
    # Eligibility view is the single source of truth for the "current student"
    # used by autosave and the sessions panel.

    available_courses = st.session_state.courses_df["Course Code"].tolist()
    selected_courses = st.multiselect(
        "Select Courses",
        options=available_courses,
        default=available_courses,
        key="indiv_courses",
    )

    # Build status codes for this student (includes Optional = 'o' and Repeat = 'ar')
    data = {"ID": [sid], "NAME": [row["NAME"]]}
    sel = st.session_state.advising_selections.get(sid, {})
    advised_list = sel.get("advised", []) or []
    optional_list = sel.get("optional", []) or []
    repeat_list = sel.get("repeat", []) or []

    # Get bypasses for this student
    major = st.session_state.get("current_major", "")
    bypasses_key = f"bypasses_{major}"
    all_bypasses = st.session_state.get(bypasses_key, {})
    student_bypasses = all_bypasses.get(sid) or all_bypasses.get(str(sid)) or {}

    # Use cached mutual_pairs
    cached = _get_fsv_cache(major)
    mutual_pairs = cached["mutual_pairs"]

    for c in selected_courses:
        if c in repeat_list:
            data[c] = ["ar"]
        elif check_course_completed(row_original, c):
            data[c] = ["c"]
        elif check_course_registered(row_original, c):
            data[c] = ["r"]
        elif c in optional_list:
            data[c] = ["o"]
        elif c in advised_list:
            data[c] = ["a"]
        else:
            stt, _ = check_eligibility(
                row_original,
                c,
                advised_list,
                st.session_state.courses_df,
                registered_courses=[],
                mutual_pairs=mutual_pairs,
                bypass_map=student_bypasses,
            )
            if stt == "Eligible (Bypass)":
                data[c] = ["b"]
            else:
                data[c] = ["na" if stt == "Eligible" else "ne"]

    indiv_df = pd.DataFrame(data)
    st.write(
        "*Legend:* c=Completed, r=Registered, a=Advised, ar=Advised-Repeat, o=Optional, b=Bypass, na=Eligible not chosen, ne=Not Eligible"
    )
    styled = _style_codes(indiv_df, selected_courses)
    st.dataframe(styled, width=1200)

    # Download colored sheet for this student (compact codes)
    col1, col2 = st.columns([1, 1])
    with col1:

        def _build_individual_report_bytes() -> bytes:
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                indiv_df.to_excel(writer, index=False, sheet_name="Student")
            apply_individual_compact_formatting(
                output=output, sheet_name="Student", course_cols=selected_courses
            )
            output.seek(0)
            return output.getvalue()

        st.download_button(
            "Download Individual Report",
            data=_build_individual_report_bytes(),
            file_name=f"Student_{sid}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            help="Download Excel report for this student with course status codes and colors",
        )

    with col2:
        # Email advising sheet to student
        if st.button(
            "📧 Email Advising Sheet",
            key=f"email_indiv_{sid}",
            help="Send this student's advising recommendations via email",
        ):
            from email_manager import get_student_email, send_advising_email

            student_email = get_student_email(str(sid))
            if not student_email:
                st.error(
                    f"No email address found for student {sid}. Please upload email roster first."
                )
            else:
                # Get selection data
                note = sel.get("note", "")
                remaining_credits = float(row.get("# Remaining", 0) or 0)

                # Send email
                success, message = send_advising_email(
                    to_email=student_email,
                    student_name=str(row["NAME"]),
                    student_id=str(sid),
                    advised_courses=advised_list,
                    repeat_courses=repeat_list,
                    optional_courses=optional_list,
                    note=note,
                    courses_df=st.session_state.courses_df,
                    remaining_credits=int(remaining_credits),
                )

                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")

    # Download sheets for all advised students into one workbook + sync to Drive (unchanged)
    all_sel = [
        (int(k), v)
        for k, v in st.session_state.advising_selections.items()
        if v.get("advised")
    ]
    if not all_sel:
        st.info("No advised students found.")
        st.download_button(
            "Download All Advised Students Reports",
            data=b"",
            file_name="All_Advised_Students.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            disabled=True,
            help="Advise at least one student to enable the export.",
        )
        return

    def _build_all_advised_bytes() -> bytes:
        output = BytesIO()

        # Get bypasses for this major
        major = st.session_state.get("current_major", "")
        bypasses_key = f"bypasses_{major}"
        all_bypasses = st.session_state.get(bypasses_key, {})

        # Use cached mutual_pairs
        cached = _get_fsv_cache(major)
        mutual_pairs = cached["mutual_pairs"]

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for sid_, sel_ in all_sel:
                srow = st.session_state.progress_df.loc[
                    st.session_state.progress_df["ID"] == sid_
                ].iloc[0]

                # Get bypasses for this student
                student_bypasses = (
                    all_bypasses.get(sid_) or all_bypasses.get(str(sid_)) or {}
                )

                data_rows = {
                    "Course Code": [],
                    "Action": [],
                    "Eligibility Status": [],
                    "Justification": [],
                    "Bypass": [],
                }
                for cc in st.session_state.courses_df["Course Code"]:
                    status, just = check_eligibility(
                        srow,
                        cc,
                        sel_.get("advised", []),
                        st.session_state.courses_df,
                        registered_courses=[],
                        mutual_pairs=mutual_pairs,
                        bypass_map=student_bypasses,
                    )
                    bypass_note = ""
                    if check_course_completed(srow, cc):
                        action = "Completed"
                        status = "Completed"
                    elif check_course_registered(srow, cc):
                        action = "Registered"
                    elif cc in sel_.get("advised", []):
                        action = "Advised"
                    elif status == "Eligible (Bypass)":
                        action = "Eligible (Bypass)"
                        bypass_info = student_bypasses.get(cc, {})
                        bypass_note = bypass_info.get("note", "")
                        if bypass_info.get("advisor"):
                            bypass_note = (
                                f"By {bypass_info['advisor']}: {bypass_note}"
                                if bypass_note
                                else f"By {bypass_info['advisor']}"
                            )
                    else:
                        action = (
                            "Eligible not chosen"
                            if status == "Eligible"
                            else "Not Eligible"
                        )
                    data_rows["Course Code"].append(cc)
                    data_rows["Action"].append(action)
                    data_rows["Eligibility Status"].append(status)
                    data_rows["Justification"].append(just)
                    data_rows["Bypass"].append(bypass_note)
                pd.DataFrame(data_rows).to_excel(
                    writer, index=False, sheet_name=str(sid_)
                )
            index_data = []
            courses_df = st.session_state.courses_df
            for sid_, sel_ in all_sel:
                srow = st.session_state.progress_df.loc[
                    st.session_state.progress_df["ID"] == sid_
                ].iloc[0]
                advised = sel_.get("advised", [])
                optional = sel_.get("optional", [])

                advised_credits = 0
                optional_credits = 0
                for cc in advised:
                    course_info = courses_df.loc[courses_df["Course Code"] == cc]
                    if not course_info.empty:
                        cr = course_info.iloc[0].get("Credits", 0)
                        try:
                            cr = float(cr) if pd.notna(cr) else 0
                        except (ValueError, TypeError):
                            cr = 0
                        advised_credits += cr
                        if cc in optional:
                            optional_credits += cr

                index_data.append(
                    {
                        "ID": sid_,
                        "NAME": srow.get("NAME", ""),
                        "Credits Advised": int(advised_credits),
                        "Optional Credits": int(optional_credits),
                    }
                )

            index_df = pd.DataFrame(index_data)
            index_df.to_excel(writer, index=False, sheet_name="Index")

        output.seek(0)
        return output.getvalue()

    all_reports_bytes = _build_all_advised_bytes()
    download_clicked = st.download_button(
        "Download All Advised Students Reports",
        data=all_reports_bytes,
        file_name="All_Advised_Students.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        help="Download Excel workbook with individual sheets for each advised student plus an index",
    )

    if download_clicked:
        try:
            gd = _get_drive_module()
            service = gd.initialize_drive_service()
            gd.sync_file_with_drive(
                service=service,
                file_content=all_reports_bytes,
                drive_file_name="All_Advised_Students.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                parent_folder_id=st.secrets["google"]["folder_id"],
            )
            st.success(
                "✅ All Advised Students Reports synced with Google Drive successfully!"
            )
            log_info(
                "All Advised Students Reports synced with Google Drive successfully."
            )
        except Exception as e:
            st.error(f"❌ Error syncing All Advised Students Reports: {e}")
            log_error("Error syncing All Advised Students Reports", e)


def _render_qaa_sheet():
    """
    QAA Sheet: Per-course summary with eligibility, advising status, and graduation metrics.
    """
    st.markdown("### 📋 QAA Sheet")
    st.markdown(
        "Quality Assurance & Analysis sheet showing per-course advising metrics."
    )

    courses_df = st.session_state.courses_df
    progress_df = st.session_state.progress_df.copy()
    advising_selections = st.session_state.get("advising_selections", {})

    progress_df["ID"] = pd.to_numeric(progress_df["ID"], errors="coerce")
    progress_df = progress_df.dropna(subset=["ID"])
    progress_df["ID"] = progress_df["ID"].astype(int)

    progress_df["Remaining Credits"] = (
        pd.to_numeric(progress_df.get("# Remaining", 0), errors="coerce")
        .fillna(0)
        .astype(int)
    )

    major = st.session_state.get("current_major", "")
    cached = _get_fsv_cache(major)
    mutual_pairs = cached["mutual_pairs"]

    bypasses_key = f"bypasses_{major}"
    all_bypasses = st.session_state.get(bypasses_key, {})

    graduating_threshold = st.slider(
        "Graduating Threshold (Remaining Credits)",
        min_value=12,
        max_value=60,
        value=36,
        step=6,
        help="Students with this many or fewer remaining credits are considered 'graduating soon'",
    )

    st.markdown("---")

    students_with_sessions = set()
    for sid in advising_selections.keys():
        try:
            students_with_sessions.add(int(sid))
        except (ValueError, TypeError):
            students_with_sessions.add(str(sid))

    all_courses = courses_df["Course Code"].dropna().unique().tolist()

    qaa_data = []

    for course_code in all_courses:
        course_info = courses_df.loc[courses_df["Course Code"] == course_code]
        if course_info.empty:
            continue

        course_name = str(course_info.iloc[0].get("Course Name", ""))

        eligible_students = []
        advised_students = []
        optional_advised_students = []
        not_advised_students = []
        skipped_advising_students = []
        attended_graduating = []
        skipped_graduating = []

        for _, student in progress_df.iterrows():
            sid = int(student["ID"])
            remaining = student.get("Remaining Credits", 999)
            is_graduating = remaining <= graduating_threshold

            if check_course_completed(student, course_code):
                continue
            if check_course_registered(student, course_code):
                continue

            student_bypasses = all_bypasses.get(sid) or all_bypasses.get(str(sid)) or {}

            sel = (
                advising_selections.get(sid) or advising_selections.get(str(sid)) or {}
            )
            student_advised = sel.get("advised", [])

            status, _ = check_eligibility(
                student,
                course_code,
                student_advised,
                courses_df,
                registered_courses=[],
                ignore_offered=True,
                mutual_pairs=mutual_pairs,
                bypass_map=student_bypasses,
            )

            is_eligible = status in ["Eligible", "Eligible (Bypass)"]

            if not is_eligible:
                continue

            eligible_students.append(sid)

            has_any_session_content = bool(
                sel.get("advised")
                or sel.get("optional")
                or sel.get("repeat")
                or sel.get("note", "").strip()
            )
            has_session = sid in students_with_sessions and has_any_session_content

            is_advised = course_code in student_advised
            student_optional = sel.get("optional", [])
            is_optional = course_code in student_optional

            if is_advised:
                advised_students.append(sid)
                if is_optional:
                    optional_advised_students.append(sid)
            elif has_session:
                not_advised_students.append(sid)
            else:
                skipped_advising_students.append(sid)

            if is_graduating:
                if has_session:
                    attended_graduating.append(sid)
                else:
                    skipped_graduating.append(sid)

        qaa_data.append(
            {
                "Course Code": course_code,
                "Course Name": course_name,
                "Eligibility": len(eligible_students),
                "Advised": len(advised_students),
                "Optional": len(optional_advised_students),
                "Not Advised": len(not_advised_students),
                "Skipped Advising": len(skipped_advising_students),
                "Attended + Graduating": len(attended_graduating),
                "Skipped + Graduating": len(skipped_graduating),
            }
        )

    if not qaa_data:
        st.info("No course data available.")
        return

    qaa_df = pd.DataFrame(qaa_data)

    qaa_df = qaa_df.sort_values(by=["Eligibility", "Advised"], ascending=[False, False])

    st.markdown(
        f"**{len(qaa_df)} courses** analyzed across **{len(progress_df)} students**"
    )
    st.markdown(
        f"Students with advising sessions: **{len(students_with_sessions)}** | Students without: **{len(progress_df) - len(students_with_sessions)}**"
    )

    st.dataframe(qaa_df, width=1200, height=min(600, 50 + len(qaa_df) * 35))

    def _build_qaa_excel() -> bytes:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            qaa_df.to_excel(writer, index=False, sheet_name="QAA Sheet")
        output.seek(0)
        return output.getvalue()

    st.download_button(
        label="📥 Download QAA Sheet (Excel)",
        data=_build_qaa_excel(),
        file_name=f"QAA_Sheet_{major}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_qaa_sheet",
        help="Download per-course metrics: eligibility counts, advising stats, and graduation data",
    )


def _render_schedule_conflict():
    """Render Schedule Conflict Insights tab."""
    st.markdown("### 📅 Schedule Conflict Insights")
    st.markdown(
        "Based on advised courses (excluding optional), these course combinations are being taken together "
        "by students and **should not conflict** in the schedule."
    )

    major = st.session_state.get("current_major", "")
    if major and "majors" in st.session_state and major in st.session_state.majors:
        advising_selections = st.session_state.majors[major].get(
            "advising_selections", {}
        )
    else:
        advising_selections = st.session_state.get("advising_selections", {})

    if not advising_selections:
        st.info(
            "No advising sessions found. Advise students first to see schedule conflict insights."
        )
        return

    def _count_non_optional_advised(sel: dict) -> int:
        advised = sel.get("advised", [])
        optional = sel.get("optional", [])
        return len([c for c in advised if c not in optional])

    students_with_advised = sum(
        1
        for sel in advising_selections.values()
        if _count_non_optional_advised(sel) >= 2
    )

    if students_with_advised == 0:
        st.info("No students have been advised for 2+ non-optional courses yet.")
        return

    cache_key = f"_conflict_combos_cache_{major}"

    all_advised_courses = []
    for sid, sel in sorted(advising_selections.items(), key=lambda x: str(x[0])):
        advised = sel.get("advised", [])
        optional = sel.get("optional", [])
        advised_only = sorted([c for c in advised if c not in optional])
        all_advised_courses.append(f"{sid}:{','.join(advised_only)}")
    version_hash = hash(tuple(all_advised_courses))

    version_key = f"{cache_key}_version"
    students_processed_key = f"{cache_key}_students_processed"

    cache_valid = (
        cache_key in st.session_state
        and st.session_state.get(version_key) == version_hash
    )

    if not cache_valid:
        combo_data, students_processed = _build_schedule_combinations(
            advising_selections
        )
        st.session_state[cache_key] = combo_data
        st.session_state[students_processed_key] = students_processed
        st.session_state[version_key] = version_hash

    combo_data = st.session_state[cache_key]
    students_processed = st.session_state.get(students_processed_key, 0)

    st.caption(
        f"Students processed (with 2+ non-optional advised courses): **{students_processed}**"
    )

    if not combo_data:
        st.info("No course combinations found.")
        return

    st.markdown("#### Merging Controls")
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        target_groups = st.slider(
            "Target max groups",
            min_value=1,
            max_value=max(50, len(combo_data)),
            value=min(10, len(combo_data)),
            help="Merge overlapping course sets until this target count is reached.",
            key="sc_target_groups",
        )

    with col2:
        max_courses_per_group = st.slider(
            "Target max courses per group",
            min_value=2,
            max_value=20,
            value=10,
            help="Stop merging a group once it reaches this many courses.",
            key="sc_max_courses",
        )

    with col3:
        st.write("")
        if st.button(
            "🔄 Refresh",
            key="sc_refresh",
            help="Recalculate schedule combinations from current advising data",
        ):
            combo_data, students_processed = _build_schedule_combinations(
                advising_selections
            )
            st.session_state[cache_key] = combo_data
            st.session_state[students_processed_key] = students_processed
            st.session_state[version_key] = version_hash
            st.rerun()

    courses_df = st.session_state.get("courses_df", pd.DataFrame())
    merged_data = _merge_schedule_groups(
        combo_data, target_groups, max_courses_per_group, courses_df
    )

    st.caption(f"Original groups: {len(combo_data)} → Merged: {len(merged_data)}")

    st.markdown("#### Filters")
    col_f1, col_f2 = st.columns(2)

    max_students_merged = (
        max(c["# Students"] for c in merged_data) if merged_data else 1
    )
    max_courses_merged = max(c["# Courses"] for c in merged_data) if merged_data else 2

    with col_f1:
        if max_students_merged > 1:
            min_students = st.slider(
                "Minimum students",
                min_value=1,
                max_value=max_students_merged,
                value=1,
                key="sc_min_students",
            )
        else:
            min_students = 1
            st.info("Showing groups with at least 1 student.")
    with col_f2:
        if max_courses_merged > 2:
            min_courses = st.slider(
                "Minimum courses",
                min_value=2,
                max_value=max(2, max_courses_merged),
                value=2,
                key="sc_min_courses",
            )
        else:
            min_courses = 2
            st.info("Showing groups with at least 2 courses.")

    filtered = [
        c
        for c in merged_data
        if c["# Students"] >= min_students and c["# Courses"] >= min_courses
    ]

    if not filtered:
        st.info(f"No combinations meet the filters.")
    else:
        st.markdown(f"**{len(filtered)} course combinations** should not conflict:")

        display_df = pd.DataFrame(filtered)
        st.dataframe(
            display_df,
            width=1200,
            height=min(500, 50 + len(filtered) * 35),
            column_config={
                "Courses": st.column_config.TextColumn("Courses", width="large"),
            },
        )

        def _build_csv() -> bytes:
            output = BytesIO()
            pd.DataFrame(filtered).to_csv(output, index=False)
            return output.getvalue()

        st.download_button(
            label="📥 Download CSV",
            data=_build_csv(),
            file_name=f"schedule_conflict_{major}.csv",
            mime="text/csv",
            key="sc_download",
        )


def _build_schedule_combinations(advising_selections: dict):
    """Build all course combinations from advising selections."""
    progress_df = st.session_state.get("progress_df", pd.DataFrame())
    courses_df = st.session_state.get("courses_df", pd.DataFrame())

    if progress_df.empty:
        return [], 0

    mutual_pairs = (
        get_mutual_concurrent_pairs(courses_df) if not courses_df.empty else set()
    )

    raw_combinations = {}
    students_processed = 0

    for student_id, selections in advising_selections.items():
        advised = selections.get("advised", [])
        optional = selections.get("optional", [])

        advised_only = sorted([c for c in advised if c not in optional])

        if len(advised_only) < 2:
            continue

        students_processed += 1
        student_name = _get_student_name_for_conflict(student_id, progress_df)

        combo_key = tuple(advised_only)
        if combo_key not in raw_combinations:
            raw_combinations[combo_key] = []
        raw_combinations[combo_key].append((student_id, student_name))

    if not raw_combinations:
        return [], students_processed

    all_combos = list(raw_combinations.keys())
    superset_map = {}

    for combo in all_combos:
        combo_set = set(combo)
        supersets_at_min_size = []
        min_size = float("inf")

        for other in all_combos:
            if other == combo:
                continue
            other_set = set(other)
            if combo_set.issubset(other_set):
                if len(other) < min_size:
                    min_size = len(other)
                    supersets_at_min_size = [other]
                elif len(other) == min_size:
                    supersets_at_min_size.append(other)

        if len(supersets_at_min_size) == 1:
            superset_map[combo] = supersets_at_min_size[0]

    def find_final_target(combo):
        visited = set()
        current = combo
        while current in superset_map and current not in visited:
            visited.add(current)
            current = superset_map[current]
        return current

    merged_data = {}
    for combo, students in raw_combinations.items():
        target = find_final_target(combo)
        if target not in merged_data:
            merged_data[target] = []
        merged_data[target].extend(students)

    results = []
    for combo_key, students in sorted(
        merged_data.items(), key=lambda x: (-len(x[1]), -len(x[0]))
    ):
        courses_list = list(combo_key)
        has_coreq = False
        for i, c1 in enumerate(courses_list):
            for c2 in courses_list[i + 1 :]:
                if (c1, c2) in mutual_pairs or (c2, c1) in mutual_pairs:
                    has_coreq = True
                    break
            if has_coreq:
                break

        results.append(
            {
                "Courses": ", ".join(combo_key),
                "# Courses": len(combo_key),
                "# Students": len(students),
                "Students": ", ".join(s[1] for s in students),
                "_student_ids": [s[0] for s in students],
                "Has Coreq": "Yes" if has_coreq else "",
            }
        )

    return results, students_processed


def _get_student_name_for_conflict(student_id, progress_df) -> str:
    """Get student name from progress_df."""
    try:
        sid_int = int(student_id)
        student_rows = progress_df.loc[progress_df["ID"] == sid_int]
        if student_rows.empty:
            return str(student_id)
        else:
            first_name = str(student_rows.iloc[0].get("First Name", ""))
            last_name = str(student_rows.iloc[0].get("Last Name", ""))
            return f"{first_name} {last_name}".strip() or str(student_id)
    except (ValueError, TypeError):
        return str(student_id)


def _merge_schedule_groups(combo_data, target_count, max_courses, courses_df):
    """Merge overlapping course groups with constraints."""
    if len(combo_data) <= target_count:
        return combo_data

    mutual_pairs = (
        get_mutual_concurrent_pairs(courses_df) if not courses_df.empty else set()
    )

    groups = []
    for c in combo_data:
        courses_set = frozenset(c["Courses"].split(", "))
        student_ids = c.get("_student_ids", [])
        student_names = c["Students"].split(", ") if c["Students"] else []
        student_map = {}
        for idx, sid in enumerate(student_ids):
            if idx < len(student_names):
                student_map[sid] = student_names[idx]
            else:
                student_map[sid] = str(sid)
        groups.append(
            {
                "courses": courses_set,
                "student_map": student_map,
            }
        )

    def overlap_score(g1, g2):
        return len(g1["courses"] & g2["courses"])

    while len(groups) > target_count:
        best_pair = None
        best_overlap = 0

        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                merged_size = len(groups[i]["courses"] | groups[j]["courses"])
                if merged_size > max_courses:
                    continue
                overlap = overlap_score(groups[i], groups[j])
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_pair = (i, j)

        if best_overlap == 0:
            break

        i, j = best_pair
        merged_map = dict(groups[i]["student_map"])
        merged_map.update(groups[j]["student_map"])
        merged = {
            "courses": groups[i]["courses"] | groups[j]["courses"],
            "student_map": merged_map,
        }

        new_groups = [g for idx, g in enumerate(groups) if idx not in (i, j)]
        new_groups.append(merged)
        groups = new_groups

    results = []
    for g in sorted(groups, key=lambda x: (-len(x["student_map"]), -len(x["courses"]))):
        courses_list = sorted(g["courses"])
        students_list = sorted(g["student_map"].values())

        has_coreq = False
        for i, c1 in enumerate(courses_list):
            for c2 in courses_list[i + 1 :]:
                if (c1, c2) in mutual_pairs or (c2, c1) in mutual_pairs:
                    has_coreq = True
                    break
            if has_coreq:
                break

        results.append(
            {
                "Courses": ", ".join(courses_list),
                "# Courses": len(courses_list),
                "# Students": len(g["student_map"]),
                "Students": ", ".join(students_list),
                "Has Coreq": "Yes" if has_coreq else "",
            }
        )

    return results
