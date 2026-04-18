# eligibility_utils.py
# Standalone eligibility checking module with no Streamlit dependencies
# This prevents circular imports during module loading

import pandas as pd
from typing import List, Tuple, Dict, Any, Union


def _norm_cell(val: Any) -> str:
    """
    Normalize a progress cell to one of:
      - 'c'  -> completed
      - 'cr' -> currently registered (BLANK / NaN)
      - 'nc' -> not completed
    Any unexpected token is treated as 'nc'.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)) or pd.isna(val):
        return "cr"
    s = str(val).strip().lower()
    if s == "":
        return "cr"
    if s == "c":
        return "c"
    if s in {"cr", "reg"}:
        return "cr"
    if s == "nc":
        return "nc"
    return "nc"


def check_course_completed(row: pd.Series, course_code: str) -> bool:
    return _norm_cell(row.get(course_code)) == "c"


def check_course_registered(row: pd.Series, course_code: str) -> bool:
    return _norm_cell(row.get(course_code)) == "cr"


def get_student_standing(total_credits_completed: Union[float, int]) -> str:
    """Preserves original app's buckets."""
    try:
        tc = float(total_credits_completed)
    except Exception:
        tc = 0.0
    if tc >= 60:
        return "Senior"
    if tc >= 30:
        return "Junior"
    return "Sophomore"


def parse_requirements(req_str: str) -> List[str]:
    if pd.isna(req_str) or req_str is None:
        return []
    s = str(req_str).strip()
    if not s or s.upper() == "N/A":
        return []
    parts = [p.strip() for chunk in s.replace(" and ", ",").split(",") for p in chunk.split(";")]
    return [p for p in parts if p]


def is_course_offered(courses_df: pd.DataFrame, course_code: str) -> bool:
    if courses_df.empty:
        return False
    row = courses_df.loc[courses_df["Course Code"] == course_code]
    if row.empty:
        return False
    return str(row["Offered"].iloc[0]).strip().lower() == "yes"


def build_requisites_str(course_info: Union[pd.Series, Dict[str, Any]]) -> str:
    pieces = []
    for key, prefix in [("Prerequisite", "Prereq"), ("Concurrent", "Conc"), ("Corequisite", "Coreq")]:
        value = course_info.get(key, "")
        if pd.isna(value) or str(value).strip() in ("", "N/A"):
            continue
        pieces.append(f"{prefix}: {str(value).strip()}")
    return "; ".join(pieces) if pieces else "None"


def get_corequisite_and_concurrent_courses(courses_df: pd.DataFrame) -> List[str]:
    """
    Returns a list of courses that appear as co-requisites or concurrent requirements
    for other courses.
    """
    coreq_concurrent_courses = set()
    
    for _, row in courses_df.iterrows():
        if "Corequisite" in row and not pd.isna(row["Corequisite"]):
            coreqs = parse_requirements(row["Corequisite"])
            coreq_concurrent_courses.update(coreqs)
        
        if "Concurrent" in row and not pd.isna(row["Concurrent"]):
            concurrents = parse_requirements(row["Concurrent"])
            coreq_concurrent_courses.update(concurrents)
    
    return sorted(list(coreq_concurrent_courses))


def get_mutual_concurrent_pairs(courses_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Detect mutual concurrent/corequisite pairs where Course A requires Course B
    AND Course B requires Course A (either as concurrent or corequisite).
    
    Returns dict mapping course_code -> list of mutually required courses.
    """
    requires_map = {}
    for _, row in courses_df.iterrows():
        course_code = row.get("Course Code", "")
        if not course_code:
            continue
        
        requirements = set()
        
        if "Corequisite" in row and not pd.isna(row["Corequisite"]):
            coreqs = parse_requirements(row["Corequisite"])
            requirements.update(coreqs)
        
        if "Concurrent" in row and not pd.isna(row["Concurrent"]):
            concurrents = parse_requirements(row["Concurrent"])
            requirements.update(concurrents)
        
        requires_map[course_code] = requirements
    
    mutual_pairs = {}
    for course_a, reqs_a in requires_map.items():
        mutual_courses = []
        for course_b in reqs_a:
            if course_b in requires_map and course_a in requires_map[course_b]:
                mutual_courses.append(course_b)
        
        if mutual_courses:
            mutual_pairs[course_a] = mutual_courses
    
    return mutual_pairs


def _standing_satisfies(req: str, standing: str) -> bool:
    req_l = req.strip().lower()
    if "senior" in req_l:
        return standing == "Senior"
    if "junior" in req_l:
        return standing in ("Junior", "Senior")
    if "sophomore" in req_l:
        return standing in ("Sophomore", "Junior", "Senior")
    return False


def check_eligibility(
    student_row: pd.Series,
    course_code: str,
    advised_courses: List[str],
    courses_df: pd.DataFrame,
    registered_courses: List[str] = None,
    ignore_offered: bool = False,
    mutual_pairs: Dict[str, List[str]] = None,
    bypass_map: Dict[str, Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Returns (status, justification).
    status in {'Eligible','Not Eligible','Completed','Registered','Eligible (Bypass)'}

    As agreed: *currently registered* satisfies requisites and is **noted**.
    
    registered_courses: List of courses the student is registered for (including simulated).
                        Used for concurrent/corequisite checks only, NOT prerequisites.
    ignore_offered: If True, skip the "Course not offered" check. Used by Full Student View
                    for planning purposes where offered status doesn't matter.
    mutual_pairs: Dict mapping course_code -> list of mutually required courses.
                  If provided, mutual concurrent/corequisite pairs are treated as eligible.
    bypass_map: Dict mapping course_code -> bypass info dict with keys:
                {note: str, advisor: str, timestamp: str}. If a course has a bypass,
                requisite checks are skipped and course is marked as "Eligible (Bypass)".
    """
    if registered_courses is None:
        registered_courses = []
    if mutual_pairs is None:
        mutual_pairs = {}
    if bypass_map is None:
        bypass_map = {}
    
    if check_course_completed(student_row, course_code):
        return "Completed", "Already completed."
    if check_course_registered(student_row, course_code):
        return "Registered", "Already registered for this course."
    
    # Check for bypass - allows student to skip requisite checks
    if course_code in bypass_map:
        bypass_info = bypass_map[course_code]
        bypass_note = bypass_info.get("note", "")
        bypass_advisor = bypass_info.get("advisor", "")
        justification = "Bypass granted"
        if bypass_advisor:
            justification += f" by {bypass_advisor}"
        if bypass_note:
            justification += f": {bypass_note}"
        else:
            justification += "."
        
        # Still check if course exists and is offered (unless ignore_offered)
        course_row = courses_df.loc[courses_df["Course Code"] == course_code]
        if course_row.empty:
            return "Not Eligible", "Course not found in courses table."
        if not ignore_offered and not is_course_offered(courses_df, course_code):
            return "Not Eligible", f"Bypass granted but course not offered. {justification}"
        
        return "Eligible (Bypass)", justification

    course_row = courses_df.loc[courses_df["Course Code"] == course_code]
    if course_row.empty:
        return "Not Eligible", "Course not found in courses table."

    standing = get_student_standing(
        float(student_row.get("# of Credits Completed", 0)) + float(student_row.get("# Registered", 0))
    )
    reasons: List[str] = []
    notes: List[str] = []
    mutual_notes: List[str] = []

    if not ignore_offered and not is_course_offered(courses_df, course_code):
        reasons.append("Course not offered.")

    def _satisfies_prerequisite(token: str) -> bool:
        """Prerequisites require completed or registered courses only - advised courses don't count."""
        tok = token.strip()
        if "standing" in tok.lower():
            return _standing_satisfies(tok, standing)
        comp = check_course_completed(student_row, tok)
        reg = check_course_registered(student_row, tok)
        if reg:
            notes.append(f"Prerequisite '{tok}' satisfied by current registration.")
        return comp or reg
    
    def _satisfies_concurrent_or_coreq(token: str, is_mutual: bool = False) -> bool:
        tok = token.strip()
        if "standing" in tok.lower():
            return _standing_satisfies(tok, standing)
        comp = check_course_completed(student_row, tok)
        reg = check_course_registered(student_row, tok)
        adv = tok in (advised_courses or [])
        sim = tok in (registered_courses or [])
        if reg or sim:
            notes.append(f"Requirement '{tok}' satisfied by current registration.")
        if is_mutual and not (comp or reg or adv or sim):
            mutual_notes.append(tok)
            return True
        return comp or reg or adv or sim

    prereq_str = course_row["Prerequisite"].iloc[0] if "Prerequisite" in course_row.columns else ""
    prereqs = parse_requirements(prereq_str)
    for r in prereqs:
        if not _satisfies_prerequisite(r):
            reasons.append(f"Prerequisite '{r}' not satisfied.")
    
    my_mutual_courses = mutual_pairs.get(course_code, [])
    
    for col, label in [
        ("Concurrent", "Concurrent requirement"),
        ("Corequisite", "Corequisite"),
    ]:
        reqs = parse_requirements(course_row[col].iloc[0] if col in course_row.columns else "")
        for r in reqs:
            is_mutual = r in my_mutual_courses
            if not _satisfies_concurrent_or_coreq(r, is_mutual=is_mutual):
                reasons.append(f"{label} '{r}' not satisfied.")

    if reasons:
        just = "; ".join(reasons)
        if notes:
            just += " " + " ".join(notes)
        return "Not Eligible", just

    justification = "All requirements met."
    if mutual_notes:
        paired = ", ".join(mutual_notes)
        justification = f"Must be taken with: {paired}."
    if notes:
        justification += " " + " ".join(notes)
    return "Eligible", justification
