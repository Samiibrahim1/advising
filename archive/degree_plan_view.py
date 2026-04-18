# degree_plan_view.py

import streamlit as st
import pandas as pd
from advising_utils import check_eligibility, get_mutual_concurrent_pairs, get_student_selections


def degree_plan_view():
    """Render semester-by-semester degree plan with student progress tracking."""
    st.markdown("## 🎓 Degree Plan Progression")
    st.markdown("Semester-by-semester curriculum showing student progress")
    
    courses_df = st.session_state.courses_df
    progress_df = st.session_state.progress_df
    
    if courses_df.empty:
        st.warning("No course data available. Please upload courses table.")
        return
    
    if progress_df.empty:
        st.info("No student data available. Upload progress report to see student progression.")
        _render_empty_degree_plan(courses_df)
        return
    
    # Student selector
    st.markdown("### Select Student")
    
    # Build student display list (NAME — ID)
    students_df = progress_df.copy()
    students_df["DISPLAY"] = students_df["NAME"].astype(str) + " — " + students_df["ID"].astype(str)
    student_displays = students_df["DISPLAY"].unique().tolist()
    
    if not student_displays:
        st.warning("No students found in progress data.")
        _render_empty_degree_plan(courses_df)
        return
    
    selected_display = st.selectbox(
        "Student",
        options=student_displays,
        key="degree_plan_student_selector"
    )
    
    # Get student progress
    student_data = students_df[students_df["DISPLAY"] == selected_display].iloc[0]
    
    # Display student info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Student ID", student_data.get("ID", "N/A"))
    with col2:
        st.metric("Standing", student_data.get("Standing", "N/A"))
    with col3:
        remaining_credits = student_data.get("Remaining Credits", 0)
        st.metric("Credits Remaining", int(remaining_credits) if pd.notna(remaining_credits) else "N/A")
    
    st.markdown("---")
    
    # Render degree plan with student progress
    _render_degree_plan_with_progress(courses_df, student_data)


def _render_empty_degree_plan(courses_df):
    """Render degree plan structure without student progress."""
    st.markdown("### Degree Plan Structure")
    st.info("Upload student progress data to see individual progression through the degree plan.")
    
    # Get semester structure
    semesters = _get_semester_structure(courses_df)
    
    if not semesters:
        st.warning("⚠️ No 'Suggested Semester' column found in courses table. Please add a column with format like 'Fall-1', 'Spring-2', etc.")
        return
    
    # Group by year
    year_groups = _group_semesters_by_year(semesters)
    
    # Render each year
    for year_name, semester_list in sorted(year_groups.items()):
        with st.expander(f"**{year_name}**", expanded=False):
            for semester_key in semester_list:
                semester_courses = semesters.get(semester_key, [])
                st.markdown(f"**{semester_key}** ({sum(c['credits'] for c in semester_courses)} credits)")
                if semester_courses:
                    for course in semester_courses:
                        st.markdown(f"  - **{course['code']}** - {course['title']} ({course['credits']} cr)")
                else:
                    st.caption("  No courses assigned")


def _group_semesters_by_year(semesters):
    """Group semester keys by year for organized display.
    
    Args:
        semesters: Dict with keys like 'Fall-1', 'Spring-2', etc.
    
    Returns:
        Dict mapping year names to list of semester keys
    """
    year_groups = {}
    
    for semester_key in semesters.keys():
        if '-' in semester_key:
            parts = semester_key.split('-')
            if len(parts) == 2:
                year_num = parts[1].strip()
                year_name = f"Year {year_num}"
                
                if year_name not in year_groups:
                    year_groups[year_name] = []
                
                year_groups[year_name].append(semester_key)
    
    # Sort semesters within each year (Fall, Spring, Summer)
    semester_order = {'fall': 0, 'spring': 1, 'summer': 2}
    for year_name in year_groups:
        year_groups[year_name].sort(
            key=lambda x: semester_order.get(x.split('-')[0].lower(), 99)
        )
    
    return year_groups


def _render_degree_plan_with_progress(courses_df, student_data):
    """Render degree plan with student progress color coding."""
    
    # Get semester structure
    semesters = _get_semester_structure(courses_df)
    
    if not semesters:
        st.warning("⚠️ No 'Suggested Semester' column found in courses table. Please add a column with format like 'Fall-1', 'Spring-2', etc.")
        return
    
    # Get student course statuses
    course_statuses = _get_student_course_statuses(student_data, courses_df)
    
    # Legend
    st.markdown("### Progress Legend")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown("🟢 **Completed**")
    with col2:
        st.markdown("🟡 **Registered**")
    with col3:
        st.markdown("🔵 **Available**")
    with col4:
        st.markdown("🟠 **Advised**")
    with col5:
        st.markdown("⚪ **Not Eligible**")
    
    st.markdown("---")
    
    # Render semester grid
    st.markdown("### Semester-by-Semester Progression")
    
    # Group semesters by year
    year_groups = _group_semesters_by_year(semesters)
    
    for year_name, semester_list in sorted(year_groups.items()):
        st.markdown(f"#### {year_name}")
        
        # Create columns for each semester in the year
        cols = st.columns(len(semester_list))
        
        for idx, semester_key in enumerate(semester_list):
            with cols[idx]:
                st.markdown(f"**{semester_key}**")
                
                semester_courses = semesters.get(semester_key, [])
                total_credits = sum(course['credits'] for course in semester_courses)
                st.caption(f"Total: {total_credits} credits")
                
                if semester_courses:
                    for course in semester_courses:
                        course_code = course['code']
                        status = course_statuses.get(course_code, 'not_eligible')
                        
                        # Get status icon and color
                        icon, color = _get_status_display(status)
                        
                        # Display course box
                        st.markdown(
                            f"{icon} **{course_code}**<br>"
                            f"<small>{course['title']}</small><br>"
                            f"<small>{course['credits']} cr</small>",
                            unsafe_allow_html=True
                        )
                        st.markdown("")  # Spacing
                else:
                    st.caption("No courses")
        
        st.markdown("---")


def _get_semester_structure(courses_df):
    """Parse semester structure from courses table.
    
    Expects a 'Suggested Semester' column with format: 'Fall-1', 'Spring-2', 'Summer-3', etc.
    """
    
    # Find the Suggested Semester column
    semester_col = None
    for col in courses_df.columns:
        if 'suggested' in col.lower() and 'semester' in col.lower():
            semester_col = col
            break
    
    if not semester_col:
        # No suggested semester column found - return empty structure with warning
        return {}
    
    # Parse semester-year format from the column
    semesters = {}
    
    for _, course_row in courses_df.iterrows():
        semester_value = str(course_row.get(semester_col, "")).strip()
        
        if not semester_value or pd.isna(semester_value):
            continue
        
        # Parse format like "Fall-1", "Spring-2", "Summer-3"
        if '-' in semester_value:
            parts = semester_value.split('-')
            if len(parts) == 2:
                semester_name = parts[0].strip()
                year_num = parts[1].strip()
                
                # Create semester key (e.g., "Fall-1")
                semester_key = f"{semester_name}-{year_num}"
                
                if semester_key not in semesters:
                    semesters[semester_key] = []
                
                semesters[semester_key].append({
                    'code': course_row["Course Code"],
                    'title': course_row.get("Course Title", course_row.get("Title", "")),
                    'credits': course_row.get("Credits", 3),
                    'semester': semester_name,
                    'year': year_num
                })
    
    return semesters


def _get_student_course_statuses(student_data, courses_df):
    """Determine status of each course for the student."""
    
    statuses = {}
    mutual_pairs = get_mutual_concurrent_pairs(courses_df)
    
    for _, course_row in courses_df.iterrows():
        course_code = course_row["Course Code"]
        
        # Check if student has taken/is taking this course
        student_status = student_data.get(course_code, "")
        
        # Check advising selections
        sid = student_data.get("ID")
        slot = get_student_selections(sid)
        
        advised = slot.get("advised", [])
        repeat = slot.get("repeat", [])
        optional = slot.get("optional", [])
        
        if pd.isna(student_status) or student_status == "":
            if course_code in advised or course_code in optional:
                statuses[course_code] = 'advised'
            elif course_code in repeat:
                statuses[course_code] = 'advised_repeat'
            else:
                # Not taken - check if eligible
                status, _ = check_eligibility(
                    student_data,
                    course_code,
                    [],
                    courses_df,
                    registered_courses=[],
                    ignore_offered=True,
                    mutual_pairs=mutual_pairs
                )
                statuses[course_code] = 'available' if status == "Eligible" else 'not_eligible'
        elif student_status.lower() in ['c', 'completed', 'pass', 'p']:
            statuses[course_code] = 'completed'
        elif student_status.lower() in ['r', 'registered', 'current']:
            statuses[course_code] = 'registered'
        elif student_status.lower() in ['f', 'fail', 'failed']:
            statuses[course_code] = 'failed'
        else:
            # Other status - check if advised
            if course_code in advised or course_code in optional:
                statuses[course_code] = 'advised'
            elif course_code in repeat:
                statuses[course_code] = 'advised_repeat'
            else:
                statuses[course_code] = 'available'
    
    return statuses


def _get_status_display(status):
    """Get display icon and color for course status."""
    
    status_map = {
        'completed': ('🟢', 'green'),
        'registered': ('🟡', 'yellow'),
        'advised': ('🟠', 'orange'),
        'advised_repeat': ('☢️', 'orange'),
        'available': ('🔵', 'blue'),
        'not_eligible': ('⚪', 'gray'),
        'failed': ('🔴', 'red')
    }
    
    return status_map.get(status, ('⚪', 'gray'))
