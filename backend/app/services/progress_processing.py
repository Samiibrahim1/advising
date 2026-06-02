"""Academic progress processing engine.

Ported from archive/course_mapping/ — all Streamlit references removed.
This module is pure Python / pandas with no framework dependencies.
"""
from __future__ import annotations

import io
from typing import Any

import pandas as pd

# ──────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────

GRADE_ORDER: list[str] = [
    "CR",
    "A+", "A", "A-",
    "B+", "B", "B-",
    "C+", "C", "C-",
    "D+", "D", "D-",
]

CELL_COLORS: dict[str, str] = {
    "c":  "#28a745",   # green  — completed
    "cr": "#FFFACD",   # yellow — currently registered
    "nc": "#f8d7da",   # red    — not completed
}

# ──────────────────────────────────────────────────────────────────
# File parsing helpers
# ──────────────────────────────────────────────────────────────────

def read_progress_report(content: bytes, filename: str) -> pd.DataFrame:
    """
    Parse uploaded progress-report bytes (Excel or CSV).

    Accepts:
    - Long format: columns [ID, NAME, Course, Grade, Year, Semester]
    - Wide format: columns [ID, NAME, COURSE_*] with cells like 'CODE/SEM-YEAR/GRADE'

    Returns standardised long-format DataFrame.
    Raises ValueError with a human-readable message on parse failure.
    """
    fname = filename.lower()
    if fname.endswith(('.xlsx', '.xls')):
        buf = io.BytesIO(content)
        xls = pd.ExcelFile(buf)
        sheet = 'Progress Report' if 'Progress Report' in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=sheet)
    elif fname.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(content))
    else:
        raise ValueError("Unsupported file format. Upload an Excel (.xlsx/.xls) or CSV (.csv) file.")

    if {'Course', 'Grade', 'Year', 'Semester'}.issubset(df.columns):
        return _normalise_long(df)
    return _transform_wide(df)


def _normalise_long(df: pd.DataFrame) -> pd.DataFrame:
    id_col = _find_col(df, ('ID', 'STUDENT ID'))
    name_col = _find_col(df, ('NAME', 'Name'))
    major_col = _find_col(df, ('MAJOR', 'Major', 'major'))
    if id_col is None:
        raise ValueError("Missing ID column. Expected 'ID' or 'STUDENT ID'.")
    if name_col is None:
        raise ValueError("Missing NAME column. Expected 'NAME' or 'Name'.")
    columns = [id_col, name_col]
    if major_col is not None:
        columns.append(major_col)
    columns.extend(['Course', 'Grade', 'Year', 'Semester'])
    result = df[columns].copy()
    rename_map = {id_col: 'ID', name_col: 'NAME'}
    if major_col is not None:
        rename_map[major_col] = 'MAJOR'
    return result.rename(columns=rename_map)


def _transform_wide(df: pd.DataFrame) -> pd.DataFrame:
    id_col = _find_col(df, ('ID', 'STUDENT ID'))
    name_col = _find_col(df, ('NAME', 'Name'))
    major_col = _find_col(df, ('MAJOR', 'Major', 'major'))
    if id_col is None:
        raise ValueError("Wide-format: missing 'ID' or 'STUDENT ID' column.")
    if name_col is None:
        raise ValueError("Wide-format: missing 'NAME' column.")

    course_cols = [c for c in df.columns if c.upper().startswith('COURSE')]
    if not course_cols:
        raise ValueError(
            "File is neither long-format (Course/Grade/Year/Semester) nor wide-format (COURSE_* columns)."
        )

    id_vars = [c for c in df.columns if c not in course_cols]
    melted = df.melt(id_vars=id_vars, value_vars=course_cols, var_name='_col', value_name='_val')
    melted = melted[melted['_val'].notna() & (melted['_val'].astype(str).str.strip() != '')]

    parts = melted['_val'].astype(str).str.split('/', expand=True)
    if parts.shape[1] < 3:
        raise ValueError(
            "Wide-format cells must be 'CODE/SEM-YEAR/GRADE' (e.g. CHEM201/Fall-2022/B+)."
        )

    melted['Course'] = parts[0].str.strip().str.upper()
    melted['_semyear'] = parts[1].str.strip()
    melted['Grade'] = parts[2].str.strip().str.upper()

    sem_parts = melted['_semyear'].str.split('-', expand=True)
    if sem_parts.shape[1] < 2:
        raise ValueError("Semester-Year must be 'SEMESTER-YYYY' (e.g. Fall-2022).")

    melted['Semester'] = sem_parts[0].str.strip().str.title()
    melted['Year'] = sem_parts[1].str.strip()

    if id_col != 'ID':
        melted = melted.rename(columns={id_col: 'ID'})
    if name_col != 'NAME':
        melted = melted.rename(columns={name_col: 'NAME'})
    if major_col is not None and major_col != 'MAJOR':
        melted = melted.rename(columns={major_col: 'MAJOR'})

    columns = ['ID', 'NAME']
    if major_col is not None:
        columns.append('MAJOR')
    columns.extend(['Course', 'Grade', 'Year', 'Semester'])
    return melted[columns].drop_duplicates()


def read_course_config(content: bytes, filename: str) -> dict[str, Any]:
    """
    Parse and validate a course configuration file.

    Required columns: Course, Type, Credits, PassingGrades
    Optional columns: FromSemester, FromYear, ToSemester, ToYear

    Returns a structured dict:
      {
        "target_courses":   {course_code: credits, ...},
        "intensive_courses":{course_code: credits, ...},
        "target_rules":     {course_code: [{Credits, PassingGrades, FromOrd, ToOrd}, ...], ...},
        "intensive_rules":  {course_code: [...], ...},
      }

    Raises ValueError with newline-separated error messages on validation failures.
    """
    fname = filename.lower()
    if fname.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(io.BytesIO(content))
    elif fname.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(content))
    else:
        raise ValueError("Unsupported file format. Upload an Excel or CSV file.")

    required_cols = {'Course', 'Type', 'Credits', 'PassingGrades'}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    errors: list[str] = []

    valid_types = {'required', 'intensive'}
    df['_type_lower'] = df['Type'].astype(str).str.strip().str.lower()
    bad = df[~df['_type_lower'].isin(valid_types)]
    if not bad.empty:
        errors.append(
            f"Invalid Type values at row(s) {bad.index.tolist()} — must be 'required' or 'intensive'."
        )

    df['_course_upper'] = df['Course'].astype(str).str.strip().str.upper()
    req_courses = set(df[df['_type_lower'] == 'required']['_course_upper'])
    int_courses = set(df[df['_type_lower'] == 'intensive']['_course_upper'])
    overlap = req_courses & int_courses
    if overlap:
        errors.append(
            f"Course(s) appear in both required AND intensive: {', '.join(sorted(overlap))}."
        )

    has_dates = all(c in df.columns for c in ('FromSemester', 'FromYear', 'ToSemester', 'ToYear'))
    if has_dates:
        for course, grp in df.groupby('_course_upper'):
            if len(grp) <= 1:
                continue
            ords: list[tuple[float, float, Any]] = []
            for _, row in grp.iterrows():
                try:
                    fs = str(row.get('FromSemester', '')) if pd.notna(row.get('FromSemester')) else ''
                    fy = row.get('FromYear', 0)
                    ts = str(row.get('ToSemester', '')) if pd.notna(row.get('ToSemester')) else ''
                    ty = row.get('ToYear', 9999)
                    from_ord = semester_to_ordinal(fs, fy) if fs else float('-inf')
                    to_ord = semester_to_ordinal(ts, ty) if ts else float('inf')
                    ords.append((from_ord, to_ord, row))
                except Exception:
                    continue
            for i, (f1, t1, r1) in enumerate(ords):
                for j, (f2, t2, r2) in enumerate(ords):
                    if i >= j:
                        continue
                    if f1 <= t2 and f2 <= t1:
                        errors.append(
                            f"Course {course} has overlapping date ranges at rows {r1.name} and {r2.name}."
                        )

    if errors:
        raise ValueError('\n'.join(errors))

    target_courses: dict[str, int] = {}
    intensive_courses: dict[str, int] = {}
    target_rules: dict[str, list[dict]] = {}
    intensive_rules: dict[str, list[dict]] = {}

    for _, row in df.iterrows():
        course = row['_course_upper']
        ctype = row['_type_lower']
        credits = int(row['Credits'])
        passing = str(row['PassingGrades']).strip()

        if has_dates:
            fs = str(row.get('FromSemester', '')) if pd.notna(row.get('FromSemester')) else ''
            fy = row.get('FromYear', 0)
            ts = str(row.get('ToSemester', '')) if pd.notna(row.get('ToSemester')) else ''
            ty = row.get('ToYear', 9999)
            from_ord = semester_to_ordinal(fs, fy) if fs else -1e9
            to_ord = semester_to_ordinal(ts, ty) if ts else 1e9
        else:
            from_ord = -1e9
            to_ord = 1e9

        rule: dict[str, Any] = {
            'Credits': credits,
            'PassingGrades': passing,
            'FromOrd': from_ord,
            'ToOrd': to_ord,
        }

        if ctype == 'required':
            target_courses[course] = credits
            target_rules.setdefault(course, []).append(rule)
        else:
            intensive_courses[course] = credits
            intensive_rules.setdefault(course, []).append(rule)

    return {
        'target_courses': target_courses,
        'intensive_courses': intensive_courses,
        'target_rules': target_rules,
        'intensive_rules': intensive_rules,
    }


def _find_col(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ──────────────────────────────────────────────────────────────────
# Semester / ordinal helpers
# ──────────────────────────────────────────────────────────────────

def semester_to_ordinal(semester: str, year: Any) -> float:
    """Convert semester + year into a comparable ordinal (year*3 + {FALL:0, SPRING:1, SUMMER:2})."""
    try:
        yr = int(year)
        sem = str(semester).strip().upper()
        sem_map = {'FALL': 0, 'SPRING': 1, 'SUMMER': 2}
        return float(yr * 3 + sem_map.get(sem, 0))
    except (ValueError, TypeError):
        return float('-inf')


# ──────────────────────────────────────────────────────────────────
# Grade value helpers
# ──────────────────────────────────────────────────────────────────

def determine_course_value(
    grade: Any,
    course: str,
    courses_dict: dict,
    rules_list: list[dict],
    term_ord: float | None = None,
) -> str:
    """
    Return a display string like 'A+ | 3', 'CR | 3', 'F | 0', 'A | PASS'.

    rules_list entries: {Credits, PassingGrades, FromOrd, ToOrd}
    """
    credits = 0
    passing = ""

    if rules_list:
        matched = None
        if term_ord is not None:
            for rule in rules_list:
                from_ord = rule.get('FromOrd', float('-inf'))
                to_ord = rule.get('ToOrd', float('inf'))
                if from_ord <= term_ord <= to_ord:
                    matched = rule
                    break
        if matched is None:
            matched = rules_list[0]
        credits = matched['Credits']
        passing = matched['PassingGrades']

    if pd.isna(grade) if not isinstance(grade, str) else False:
        return f"CR | {credits}" if credits > 0 else "CR | PASS"
    grade_str = str(grade).strip()
    if grade_str == "" or grade_str.upper() in ("NAN", "NONE"):
        return f"CR | {credits}" if credits > 0 else "CR | PASS"

    tokens = [g.strip().upper() for g in grade_str.split(",") if g.strip()]
    all_toks = ", ".join(tokens)
    allowed = [x.strip().upper() for x in passing.split(",")] if passing else []
    passed = any(g in allowed for g in tokens)

    if credits > 0:
        return f"{all_toks} | {credits}" if passed else f"{all_toks} | 0"
    return f"{all_toks} | PASS" if passed else f"{all_toks} | FAIL"


def extract_primary_grade(value: str) -> str:
    """
    Pick the single highest-priority entry from a multi-attempt value string
    (CR first, then GRADE_ORDER order).
    """
    if not isinstance(value, str):
        return str(value)

    entries = [e.strip() for e in value.split(",") if e.strip()]
    parsed: list[dict[str, str]] = []
    for entry in entries:
        if "|" in entry:
            g, c = entry.split("|", 1)
            parsed.append({"grade": g.strip().upper(), "credit": c.strip(), "original": entry})
        else:
            parsed.append({"grade": entry.strip().upper(), "credit": "", "original": entry})

    for entry in parsed:
        if entry["grade"] == "CR":
            return entry["original"]

    for grade in GRADE_ORDER:
        for entry in parsed:
            if entry["grade"] == grade:
                return entry["original"]

    for entry in parsed:
        credit = entry["credit"].strip()
        if credit:
            try:
                if int(credit) > 0:
                    return entry["original"]
            except ValueError:
                if credit.upper() == "PASS":
                    return entry["original"]

    return parsed[0]["original"] if parsed else ""


def cell_color(value: str) -> str:
    """Return a CSS background-color value for the given processed cell value."""
    if not isinstance(value, str):
        return ""

    collapsed = value.strip().lower()
    color = CELL_COLORS.get(collapsed)
    if color:
        return f"background-color: {color}"

    entries = [e.strip() for e in value.split(",") if e.strip()]
    for entry in entries:
        if entry.upper().startswith("CR"):
            return f"background-color: {CELL_COLORS['cr']}"

    for entry in entries:
        parts = entry.split("|")
        if len(parts) == 2:
            right = parts[1].strip().upper()
            try:
                if int(right) > 0:
                    return f"background-color: {CELL_COLORS['c']}"
            except ValueError:
                if right == "PASS":
                    return f"background-color: {CELL_COLORS['c']}"

    return f"background-color: {CELL_COLORS['nc']}"


# ──────────────────────────────────────────────────────────────────
# Main processing pipeline
# ──────────────────────────────────────────────────────────────────

def process_progress_report(
    df: pd.DataFrame,
    target_courses: dict[str, int],
    intensive_courses: dict[str, int],
    target_rules: dict[str, list[dict]],
    intensive_rules: dict[str, list[dict]],
    per_student_assignments: dict[str, dict[str, str]] | None = None,
    equivalent_courses_mapping: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    """
    Process a long-format progress DataFrame into pivot tables.

    Returns: (required_df, intensive_df, extra_courses_df, extra_courses_list)
    Each pivot df has columns: [ID, NAME, <course_codes>...]
    """
    if equivalent_courses_mapping is None:
        equivalent_courses_mapping = {}

    df = df.copy()
    df['ID'] = df['ID'].astype(str).str.strip()

    # 1) Map equivalents
    df['Mapped Course'] = df['Course'].apply(
        lambda x: equivalent_courses_mapping.get(str(x).strip().upper(), str(x).strip().upper())
    )
    df['Assignable Course'] = df['Mapped Course']

    # 2) Apply per-student assignments
    if per_student_assignments:
        all_types = _collect_assignment_types(per_student_assignments)

        def map_assignment(row: pd.Series) -> str:
            sid = str(row['ID'])
            assigns = per_student_assignments.get(sid, {})
            for atype in all_types:
                if assigns.get(atype) == row['Mapped Course']:
                    return atype
            return row['Mapped Course']

        df['Mapped Course'] = df.apply(map_assignment, axis=1)

    # 3) Term ordinals
    df['TermOrd'] = df.apply(
        lambda r: semester_to_ordinal(r.get('Semester', ''), r.get('Year', '')), axis=1
    )

    # 4) ProcessedValue per row
    def get_processed(row: pd.Series) -> str:
        mc = row['Mapped Course']
        courses_dict = (
            target_courses if mc in target_courses
            else intensive_courses if mc in intensive_courses
            else {}
        )
        rules = (
            target_rules.get(mc, []) if mc in target_rules
            else intensive_rules.get(mc, [])
        )
        return determine_course_value(row['Grade'], mc, courses_dict, rules, row['TermOrd'])

    df['ProcessedValue'] = df.apply(get_processed, axis=1)

    # Preserve full roster so students without course rows still appear.
    roster_cols = ['ID', 'NAME']
    if 'MAJOR' in df.columns:
        roster_cols.append('MAJOR')
    roster_df = df[roster_cols].drop_duplicates(subset=['ID', 'NAME'])

    # 5) Split
    target_mask = df['Mapped Course'].isin(target_courses)
    intensive_mask = df['Mapped Course'].isin(intensive_courses)
    target_df = df[target_mask]
    intensive_df = df[intensive_mask]
    extra_df = df[~target_mask & ~intensive_mask]

    # 6) Pivot
    def _pivot(src: pd.DataFrame) -> pd.DataFrame:
        if src.empty:
            return pd.DataFrame(columns=['ID', 'NAME'])
        return src.pivot_table(
            index=['ID', 'NAME'],
            columns='Mapped Course',
            values='ProcessedValue',
            aggfunc=lambda v: ', '.join(str(x) for x in v),
        ).reset_index()

    req_pivot = roster_df.merge(_pivot(target_df), on=['ID', 'NAME'], how='left')
    int_pivot = roster_df.merge(_pivot(intensive_df), on=['ID', 'NAME'], how='left')

    # 7) Fill NR for missing courses
    for course in target_courses:
        if course not in req_pivot.columns:
            req_pivot[course] = 'NR'
        else:
            req_pivot[course] = req_pivot[course].fillna('NR')

    for course in intensive_courses:
        if course not in int_pivot.columns:
            int_pivot[course] = 'NR'
        else:
            int_pivot[course] = int_pivot[course].fillna('NR')

    base_cols = ['ID', 'NAME']
    if 'MAJOR' in roster_df.columns:
        base_cols.append('MAJOR')
    result_req = req_pivot[base_cols + list(target_courses.keys())]
    result_int = int_pivot[base_cols + list(intensive_courses.keys())]

    extra_list = sorted(extra_df['Assignable Course'].unique().tolist()) if not extra_df.empty else []
    return result_req, result_int, extra_df, extra_list


def _collect_assignment_types(per_student: dict[str, dict[str, str]]) -> list[str]:
    types: set[str] = set()
    for assigns in per_student.values():
        types.update(assigns.keys())
    return list(types)


# ──────────────────────────────────────────────────────────────────
# Credit calculations
# ──────────────────────────────────────────────────────────────────

def calculate_credits(row: pd.Series, courses_dict: dict[str, int]) -> dict[str, float]:
    """
    Tally completed / registered / remaining credits for a single student row.
    Returns {'completed': n, 'registered': n, 'remaining': n, 'total': n}
    """
    completed = registered = remaining = 0
    total = sum(courses_dict.values())

    for course, cred in courses_dict.items():
        val = str(row.get(course, 'NR'))
        entries = [e.strip() for e in val.split(',') if e.strip()]

        if any(e.upper().startswith('CR') for e in entries):
            registered += cred
            continue

        passed = False
        for e in entries:
            parts = [p.strip() for p in e.split('|')]
            if len(parts) == 2:
                try:
                    if int(parts[1]) > 0:
                        passed = True
                        break
                except ValueError:
                    if parts[1].upper() == 'PASS':
                        passed = True
                        break

        if passed:
            completed += cred
        else:
            remaining += cred

    return {
        'completed': float(completed),
        'registered': float(registered),
        'remaining': float(remaining),
        'total': float(total),
    }
