"""Bulk intensive-course placement from an uploaded report.

The placement report is a spreadsheet with two columns:
  - student_id  (or 'ID')
  - placement_course  (or 'placed_course', 'course')

Multiple rows per student are supported (e.g. one for ARAB placement, one for ENGL).

For each student the system determines which intensive courses should remain
ACTIVE (= the placement course + all of its descendants in the prerequisite chain).
Every other intensive course is set as Excluded.

Example
-------
Intensive courses: ARAB101 → ARAB201 → ARAB301
Student placed at ARAB201  →  active = {ARAB201, ARAB301}  →  ARAB101 excluded.
Any other intensive tracks (ENGL100, ENGL200, …) are also excluded unless the
student also has a separate placement row for that track.
"""
from __future__ import annotations

import io
from collections import defaultdict
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.services.dataset_service import dataset_dataframe
from app.services.student_service import replace_exclusions

# Import grouped parser from workspace-root eligibility_utils via sys.path
from pathlib import Path
import sys

_ROOT = None

def _find_root() -> Path:
    global _ROOT
    if _ROOT is not None:
        return _ROOT
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / 'eligibility_utils.py').exists():
            _ROOT = d
            return d
        d = d.parent
    raise RuntimeError('Cannot locate eligibility_utils.py')


def _ensure_path() -> None:
    root = str(_find_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def _parse_placement_file(content: bytes) -> pd.DataFrame:
    """Return a DataFrame with normalised columns student_id and placement_course.

    Multiple rows per student are preserved (one per intensive track).
    """
    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(content))
        except Exception as exc:
            raise ValueError(f'Cannot parse file: {exc}') from exc

    # Normalise column names
    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

    # Accept common alternative spellings
    col_map = {
        'id': 'student_id',
        'student': 'student_id',
        'placed_course': 'placement_course',
        'course': 'placement_course',
        'course_code': 'placement_course',
        'placement': 'placement_course',
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    missing = {'student_id', 'placement_course'} - set(df.columns)
    if missing:
        raise ValueError(
            f'Missing columns: {", ".join(sorted(missing))}. '
            'Expected columns: student_id (or ID) and placement_course (or course, placed_course).'
        )

    df['student_id'] = df['student_id'].astype(str).str.strip()
    df['placement_course'] = df['placement_course'].astype(str).str.strip()
    df = df[df['student_id'].notna() & df['placement_course'].notna()]
    df = df[df['student_id'] != '']
    df = df[df['placement_course'] != '']
    # Keep all rows — multiple placements per student are valid (one per track)
    return df[['student_id', 'placement_course']].drop_duplicates()


def _build_intensive_graph(courses_df: pd.DataFrame) -> tuple[set[str], dict[str, set[str]]]:
    """Return (intensive_codes, successors_map).

    successors_map[C] = set of intensive courses that directly list C as a
    prerequisite (i.e. immediate successors in the chain).
    """
    _ensure_path()
    from eligibility_utils import parse_requirements  # noqa: PLC0415

    type_series = courses_df.get('Type', pd.Series(dtype=str)).astype(str).str.strip().str.lower()
    intensive_codes: set[str] = set(
        courses_df.loc[type_series == 'intensive', 'Course Code'].dropna().astype(str).tolist()
    )

    # Build direct prereq graph (prereqs[C] = {direct intensive prerequisites of C})
    prereqs: dict[str, set[str]] = {c: set() for c in intensive_codes}
    for _, row in courses_df.iterrows():
        code = str(row.get('Course Code', '')).strip()
        if code not in intensive_codes:
            continue
        req_str = row.get('Prerequisite', '')
        for token in parse_requirements(req_str):
            token = token.strip()
            if token in intensive_codes:
                prereqs[code].add(token)

    # Build inverse: successors[C] = {courses that directly require C}
    successors: dict[str, set[str]] = defaultdict(set)
    for code, direct_prereqs in prereqs.items():
        for p in direct_prereqs:
            successors[p].add(code)

    return intensive_codes, dict(successors)


def _descendants(code: str, successors: dict[str, set[str]]) -> set[str]:
    """Return all transitive successors (descendants) of a course."""
    visited: set[str] = set()
    stack = list(successors.get(code, []))
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(successors.get(current, set()) - visited)
    return visited


def bulk_placement_from_file(
    session: Session,
    major_code: str,
    content: bytes,
) -> dict[str, object]:
    """Parse an intensive placement report and apply exclusions per student.

    For each student, courses that should remain ACTIVE are:
      - the placement course itself
      - all descendants of the placement course (courses it unlocks)

    All other intensive courses are set as Excluded.
    Multiple placement rows per student are supported.

    Returns ``{processed: int, errors: list[str]}``.
    Students not in the file are untouched.
    """
    df = _parse_placement_file(content)

    courses_df = dataset_dataframe(session, major_code, 'courses')
    if courses_df.empty:
        raise ValueError('No courses dataset uploaded for this major.')

    intensive_codes, successors = _build_intensive_graph(courses_df)

    # Group placements by student (preserving multiple placements per student)
    by_student: dict[str, list[str]] = defaultdict(list)
    for _, row in df.iterrows():
        by_student[str(row['student_id'])].append(str(row['placement_course']))

    processed = 0
    errors: list[str] = []

    from app.models import CourseExclusion, Major
    from sqlalchemy import select
    major = session.scalar(select(Major).where(Major.code == major_code))
    if not major:
        raise ValueError(f'Major {major_code} not found.')

    for student_id, placements in by_student.items():
        # Validate all placement courses exist as intensive
        invalid = [p for p in placements if p not in intensive_codes]
        if invalid:
            errors.append(
                f'Student {student_id}: "{", ".join(invalid)}" is not an intensive course — skipped.'
            )
            continue

        # Active = placement course(s) + all their descendants
        active_intensive: set[str] = set()
        for p in placements:
            active_intensive.add(p)
            active_intensive |= _descendants(p, successors)

        # Exclude all intensive courses NOT in the active set
        to_exclude = intensive_codes - active_intensive

        # Preserve existing non-intensive exclusions
        existing_excl = {
            row.course_code
            for row in session.scalars(
                select(CourseExclusion).where(
                    CourseExclusion.major_id == major.id,
                    CourseExclusion.student_id == student_id,
                )
            ).all()
        }
        non_intensive_excl = existing_excl - intensive_codes
        final_excl = sorted(non_intensive_excl | to_exclude)

        replace_exclusions(session, major_code, [student_id], final_excl)
        processed += 1

    return {'processed': processed, 'errors': errors}
