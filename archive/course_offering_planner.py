# course_offering_planner.py

import streamlit as st
import pandas as pd
from typing import Dict, List, Tuple, Set
from io import BytesIO
from advising_utils import (
    check_course_completed,
    check_course_registered,
    check_eligibility,
    get_mutual_concurrent_pairs,
    parse_requirements,
    build_requisites_str,
)


def course_offering_planner():
    """
    Course Offering Planner - Smart recommendation engine for semester course planning.
    Analyzes graduating students, bottlenecks, eligible counts, and cascading eligibility.
    """
    if "courses_df" not in st.session_state or st.session_state.courses_df.empty:
        st.warning("Courses table not loaded.")
        return
    if "progress_df" not in st.session_state or st.session_state.progress_df.empty:
        st.warning("Progress report not loaded.")
        return

    with st.expander("Course Offering Planner", expanded=False):
        st.markdown(
            "Data-driven recommendations for which courses to offer based on "
            "graduating students, bottleneck analysis, and cascading eligibility effects."
        )
        _render_course_offering_planner_content()


def _render_course_offering_planner_content():
    """Internal function to render the Course Offering Planner content."""
    courses_df = st.session_state.courses_df
    progress_df = st.session_state.progress_df.copy()

    # Prepare student data
    progress_df["ID"] = pd.to_numeric(progress_df["ID"], errors="coerce")
    progress_df = progress_df.dropna(subset=["ID"])
    progress_df["ID"] = progress_df["ID"].astype(int)

    # Calculate remaining credits
    progress_df["Remaining Credits"] = pd.to_numeric(
        progress_df.get("# Remaining", 0), errors="coerce"
    ).fillna(0).astype(int)

    # Get all courses
    all_courses = courses_df["Course Code"].dropna().unique().tolist()

    # --- Analysis Parameters ---
    col_params1, col_params2 = st.columns(2)
    with col_params1:
        graduation_threshold = st.slider(
            "🎓 Graduating Soon Threshold (Remaining Credits)",
            min_value=0,
            max_value=60,
            value=30,
            step=5,
            help="Students with this many or fewer remaining credits are considered 'graduating soon'"
        )
    
    with col_params2:
        min_eligible_students = st.slider(
            "👥 Minimum Eligible Students",
            min_value=1,
            max_value=20,
            value=3,
            help="Only recommend courses with at least this many eligible students"
        )

    st.markdown("---")

    # --- Core Analysis ---
    with st.spinner("Analyzing course recommendations..."):
        recommendations = _analyze_course_recommendations(
            courses_df,
            progress_df,
            all_courses,
            graduation_threshold,
            min_eligible_students
        )

    if not recommendations:
        st.info("No course recommendations found with current parameters. Try adjusting the filters.")
        return

    # Sort by priority score
    sorted_recs = sorted(recommendations, key=lambda x: x["priority_score"], reverse=True)

    # --- Top Recommendations ---
    st.markdown("### 🏆 Top 10 Recommended Courses")
    
    top_10 = sorted_recs[:10]
    for idx, rec in enumerate(top_10, 1):
        _render_course_card(rec, idx)

    st.markdown("---")

    # --- All Recommendations Table ---
    st.markdown("### 📊 All Course Recommendations")
    
    # Build summary table
    summary_data = []
    for rec in sorted_recs:
        summary_data.append({
            "Rank": rec["rank"],
            "Course": rec["course"],
            "Priority Score": f"{rec['priority_score']:.1f}",
            "Currently Eligible": rec["currently_eligible"],
            "Graduating Students": rec["graduating_students"],
            "Bottleneck Score": rec["bottleneck_score"],
            "Cascading Eligible": rec["cascading_eligible"],
            "Reason": rec["reason"]
        })
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, width=1200, height=400)

    # --- Course Selection ---
    st.markdown("---")
    st.markdown("### ✅ Select Courses to Offer")
    
    if "selected_offerings" not in st.session_state:
        st.session_state.selected_offerings = []
    
    course_options = [rec["course"] for rec in sorted_recs]
    
    selected = st.multiselect(
        "Choose courses for this semester",
        options=course_options,
        default=st.session_state.selected_offerings,
        help="Select the courses you plan to offer based on the recommendations above"
    )
    
    if st.button("💾 Save Course Offerings", type="primary"):
        st.session_state.selected_offerings = selected
        st.success(f"✅ Saved {len(selected)} courses for offering: {', '.join(selected)}")
        
        # Show impact summary
        total_eligible = sum(rec["currently_eligible"] for rec in sorted_recs if rec["course"] in selected)
        total_graduating = sum(rec["graduating_students"] for rec in sorted_recs if rec["course"] in selected)
        
        st.info(
            f"**Impact Summary:** This offering will directly serve {total_eligible} currently eligible students, "
            f"including {total_graduating} students who are graduating soon."
        )


def _analyze_course_recommendations(
    courses_df: pd.DataFrame,
    progress_df: pd.DataFrame,
    all_courses: List[str],
    graduation_threshold: int,
    min_eligible: int
) -> List[Dict]:
    """
    Analyze all courses and return prioritized recommendations.
    """
    recommendations = []
    
    # Build prerequisite dependency map (what courses unlock)
    prereq_map = _build_prerequisite_map(courses_df)
    
    # Calculate mutual pairs once for efficiency
    mutual_pairs = get_mutual_concurrent_pairs(courses_df)
    
    for course in all_courses:
        course_info = courses_df.loc[courses_df["Course Code"] == course]
        if course_info.empty:
            continue
        
        course_row = course_info.iloc[0]
        
        # Skip if already offered everywhere
        # (You might want to adjust this logic based on your needs)
        
        # Count eligible students
        eligible_students = []
        graduating_students = []
        
        for _, student in progress_df.iterrows():
            sid = int(student["ID"])
            remaining = student.get("Remaining Credits", 999)
            
            # Check if already completed or registered
            if check_course_completed(student, course) or check_course_registered(student, course):
                continue
            
            # Check eligibility
            status, _ = check_eligibility(
                student,
                course,
                [],  # No advised courses for this analysis
                courses_df,
                registered_courses=[],
                ignore_offered=True,
                mutual_pairs=mutual_pairs
            )
            
            if status == "Eligible":
                eligible_students.append(sid)
                if remaining <= graduation_threshold:
                    graduating_students.append(sid)
        
        currently_eligible = len(eligible_students)
        
        # Skip if below minimum threshold
        if currently_eligible < min_eligible:
            continue
        
        # Calculate bottleneck score (how many downstream courses this unlocks)
        bottleneck_score = len(prereq_map.get(course, []))
        
        # Calculate cascading eligibility (students who would become eligible for other courses)
        cascading_eligible = _calculate_cascading_eligibility(
            course,
            eligible_students,
            progress_df,
            courses_df,
            prereq_map
        )
        
        # Calculate priority score
        priority_score = (
            (currently_eligible * 1.0) +              # Base: number of eligible students
            (len(graduating_students) * 3.0) +        # 3x weight for graduating students
            (bottleneck_score * 2.0) +                # 2x weight for bottleneck courses
            (cascading_eligible * 1.5)                # 1.5x weight for cascading effects
        )
        
        # Build recommendation reason
        reason_parts = []
        if len(graduating_students) > 0:
            reason_parts.append(f"{len(graduating_students)} graduating")
        if bottleneck_score > 0:
            reason_parts.append(f"unlocks {bottleneck_score} courses")
        if cascading_eligible > 0:
            reason_parts.append(f"+{cascading_eligible} cascading eligible")
        
        reason = "; ".join(reason_parts) if reason_parts else "General progression"
        
        recommendations.append({
            "course": course,
            "priority_score": priority_score,
            "currently_eligible": currently_eligible,
            "graduating_students": len(graduating_students),
            "bottleneck_score": bottleneck_score,
            "cascading_eligible": cascading_eligible,
            "reason": reason,
            "requisites": build_requisites_str(course_row)
        })
    
    # Add rank
    sorted_recs = sorted(recommendations, key=lambda x: x["priority_score"], reverse=True)
    for idx, rec in enumerate(sorted_recs, 1):
        rec["rank"] = idx
    
    return sorted_recs


def _build_prerequisite_map(courses_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Build a map of course -> list of courses it is a prerequisite for.
    This helps identify bottleneck courses.
    """
    prereq_map = {}
    
    for _, course_row in courses_df.iterrows():
        course_code = course_row.get("Course Code")
        if pd.isna(course_code):
            continue
        
        # Check what this course is a prerequisite for
        prereqs = parse_requirements(course_row.get("Prerequisite", ""))
        concurrent = parse_requirements(course_row.get("Concurrent", ""))
        coreqs = parse_requirements(course_row.get("Corequisite", ""))
        
        all_reqs = set(prereqs + concurrent + coreqs)
        
        for req_course in all_reqs:
            if req_course not in prereq_map:
                prereq_map[req_course] = []
            prereq_map[req_course].append(course_code)
    
    return prereq_map


def _calculate_cascading_eligibility(
    course: str,
    eligible_student_ids: List[int],
    progress_df: pd.DataFrame,
    courses_df: pd.DataFrame,
    prereq_map: Dict[str, List[str]]
) -> int:
    """
    Calculate how many additional students would become eligible for OTHER courses
    if the eligible students take this course.
    """
    # Get courses that have this course as a prerequisite/concurrent/corequisite
    downstream_courses = prereq_map.get(course, [])
    
    if not downstream_courses:
        return 0
    
    cascading_count = 0
    mutual_pairs = get_mutual_concurrent_pairs(courses_df)
    
    for downstream_course in downstream_courses:
        for sid in eligible_student_ids:
            student_row = progress_df.loc[progress_df["ID"] == sid]
            if student_row.empty:
                continue
            
            student_row = student_row.iloc[0]
            
            # Check if they'd be eligible for downstream course AFTER taking this course
            # This is a simplified check - in reality you'd simulate completion
            status_before, _ = check_eligibility(
                student_row,
                downstream_course,
                [],
                courses_df,
                registered_courses=[],
                ignore_offered=True,
                mutual_pairs=mutual_pairs
            )
            
            status_after, _ = check_eligibility(
                student_row,
                downstream_course,
                [],
                courses_df,
                registered_courses=[course],  # Simulate having taken the prerequisite
                ignore_offered=True,
                mutual_pairs=mutual_pairs
            )
            
            # If they weren't eligible before but are now, count it
            if status_before != "Eligible" and status_after == "Eligible":
                cascading_count += 1
    
    return cascading_count


def _render_course_card(rec: Dict, rank: int):
    """
    Render a visually appealing card for a course recommendation.
    """
    # Determine color based on priority
    if rank <= 3:
        border_color = "#28a745"  # Green for top 3
    elif rank <= 7:
        border_color = "#ffc107"  # Yellow for 4-7
    else:
        border_color = "#6c757d"  # Gray for rest
    
    st.markdown(
        f"""
        <div style="border-left: 5px solid {border_color}; padding: 15px; margin-bottom: 15px; background-color: #f8f9fa; border-radius: 5px;">
            <h4 style="margin: 0 0 10px 0;">#{rank} - {rec['course']}</h4>
            <p style="margin: 5px 0; color: #666;"><strong>Priority Score:</strong> {rec['priority_score']:.1f}</p>
            <p style="margin: 5px 0;"><strong>Reason:</strong> {rec['reason']}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Currently Eligible", rec["currently_eligible"])
    with col2:
        st.metric("Graduating Students", rec["graduating_students"])
    with col3:
        st.metric("Unlocks Courses", rec["bottleneck_score"])
    with col4:
        st.metric("Cascading Impact", rec["cascading_eligible"])
    
    # Show requisites
    if rec["requisites"]:
        st.caption(f"📋 {rec['requisites']}")
