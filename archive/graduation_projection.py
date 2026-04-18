"""
Graduation Projection Module
Calculates projected graduation date based on advised course plan
"""

from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pandas as pd


def get_course_credits(course_code: str, courses_df: pd.DataFrame) -> float:
    """Get credit hours for a course"""
    if courses_df is None or courses_df.empty:
        return 0.0
    
    matching = courses_df[courses_df['Course Code'] == course_code]
    if not matching.empty:
        credits = matching.iloc[0].get('Credits', 0)
        return float(credits) if credits else 0.0
    return 0.0


def calculate_total_credits(courses: List[str], courses_df: pd.DataFrame) -> float:
    """Calculate total credits for a list of courses"""
    if not courses:
        return 0.0
    
    total = 0.0
    for course_code in courses:
        total += get_course_credits(course_code, courses_df)
    
    return total


def get_semester_sequence() -> List[Tuple[str, str]]:
    """
    Return semester sequence starting from current semester
    Returns list of (semester, year) tuples
    """
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # Determine current semester
    if current_month in [1, 2, 3, 4, 5]:
        current_semester = "Spring"
        start_year = current_year
    elif current_month in [6, 7]:
        current_semester = "Summer"
        start_year = current_year
    else:  # 8, 9, 10, 11, 12
        current_semester = "Fall"
        start_year = current_year
    
    # Semester order
    semester_order = ["Spring", "Summer", "Fall"]
    
    # Find starting index
    try:
        start_idx = semester_order.index(current_semester)
    except ValueError:
        start_idx = 0
    
    # Generate 8 semesters (2 years) worth of semester/year combos
    semesters = []
    current_sem_idx = start_idx
    current_yr = start_year
    
    for i in range(8):
        sem = semester_order[current_sem_idx % 3]
        semesters.append((sem, str(current_yr)))
        
        # Move to next semester
        current_sem_idx += 1
        if current_sem_idx % 3 == 0:  # Just finished Fall, move to Spring next year
            current_yr += 1
    
    return semesters


def project_graduation_date(
    completed_credits: float,
    advised_courses: List[str],
    optional_courses: List[str],
    repeat_courses: List[str],
    required_credits: float,
    courses_df: pd.DataFrame,
    max_credits_per_semester: float = 18.0,
    credits_per_semester: float = 15.0
) -> Dict:
    """
    Calculate projected graduation date based on course plan
    
    Args:
        completed_credits: Credits student has already completed
        advised_courses: List of advised course codes for this semester
        optional_courses: List of optional course codes for this semester
        repeat_courses: List of repeat course codes for this semester
        required_credits: Total credits needed for degree
        courses_df: DataFrame with course information
        max_credits_per_semester: Maximum credits student can register for (caps advised+optional) (default 18)
        credits_per_semester: Avg credits taken per semester for future planning (default 15)
    
    Returns:
        Dict with:
        - projected_graduation: (semester, year) tuple
        - semesters_remaining: number of semesters
        - credits_this_semester: credits for current semester plan (capped at max_credits_per_semester)
        - credits_after_this_semester: total credits after this semester
        - credits_still_needed: remaining credits after this semester
        - on_track: boolean if will graduate in expected timeframe
    """
    
    # Calculate credits for this semester
    advised_credits = calculate_total_credits(advised_courses, courses_df)
    optional_credits = calculate_total_credits(optional_courses, courses_df)
    repeat_credits = calculate_total_credits(repeat_courses, courses_df)
    
    # Cap total credits at max allowed (advised + optimal subset of optional)
    advised_and_optional = advised_credits + optional_credits
    if advised_and_optional > max_credits_per_semester:
        # Cap at max, prioritize advised courses
        credits_this_semester = max_credits_per_semester
    else:
        credits_this_semester = advised_and_optional
    
    # Add repeat courses separately (they don't count toward new requirement)
    credits_this_semester_with_repeats = credits_this_semester + repeat_credits
    credits_after_this = completed_credits + credits_this_semester
    credits_needed = max(0, required_credits - credits_after_this)
    
    # Calculate semesters needed
    if credits_needed <= 0:
        semesters_needed = 0
    else:
        semesters_needed = int((credits_needed + credits_per_semester - 1) // int(credits_per_semester))
    
    # Get semester sequence
    semesters = get_semester_sequence()
    
    # Project graduation (add 1 for current semester)
    graduation_idx = min(semesters_needed, len(semesters) - 1)
    projected_semester, projected_year = semesters[graduation_idx]
    
    # Determine if on track
    on_track = graduation_idx < len(semesters)
    
    return {
        "projected_graduation": (projected_semester, projected_year),
        "semesters_remaining": semesters_needed,
        "credits_this_semester": credits_this_semester,
        "credits_with_repeats": credits_this_semester_with_repeats,
        "credits_after_this_semester": credits_after_this,
        "credits_still_needed": credits_needed,
        "on_track": on_track,
        "graduation_text": f"{projected_semester} {projected_year}" if on_track else "Beyond projection"
    }


def format_graduation_message(projection: Dict, student_name: str = "") -> str:
    """Format graduation projection as human-readable message"""
    text = ""
    
    if student_name:
        text += f"**{student_name}**\n"
    
    text += f"📚 **Graduation Projection**: {projection['graduation_text']}\n"
    text += f"   • Semesters remaining: {projection['semesters_remaining']}\n"
    text += f"   • Credits after this semester: {projection['credits_after_this_semester']}\n"
    text += f"   • Credits this semester: {projection['credits_this_semester']}\n"
    
    if projection['credits_still_needed'] > 0:
        text += f"   • Credits still needed: {projection['credits_still_needed']}\n"
    else:
        text += f"   ✅ Will complete degree this semester!\n"
    
    return text
