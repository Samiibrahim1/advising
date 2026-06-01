from __future__ import annotations

from io import BytesIO
from pathlib import Path

import openpyxl
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.routes.datasets import _generated_dataset_workbook
from app.core.config import get_settings
from app.db import Base
from app.models import DatasetVersion, Major
from app.models.progress_models import AssignmentType, ProgressAssignment
from app.services.dataset_service import get_active_dataset
from app.services.progress_processing import process_progress_report, read_progress_report
from app.services.progress_service import generate_report, push_progress_to_advising
from app.services.storage import StorageService


def _xlsx_bytes(df: pd.DataFrame, sheet_name: str = 'Progress Report') -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buf.getvalue()


def test_generated_dataset_workbook_uses_parsed_payload():
    version = DatasetVersion(
        dataset_type='courses',
        version_label='abc123',
        original_filename='missing.xlsx',
        storage_key='missing',
        parsed_payload={'records': [{'ID': '1', 'NAME': 'Alice'}]},
        metadata_json={},
    )

    workbook_bytes = _generated_dataset_workbook(version)
    wb = openpyxl.load_workbook(BytesIO(workbook_bytes))
    ws = wb['courses']

    assert ws['A1'].value == 'ID'
    assert ws['B1'].value == 'NAME'
    assert ws['A2'].value == '1'
    assert ws['B2'].value == 'Alice'


def test_progress_report_long_format_preserves_major():
    content = _xlsx_bytes(pd.DataFrame([
        {'ID': '1', 'NAME': 'Alice', 'MAJOR': 'Engineering', 'Course': 'PBHL201', 'Grade': 'A', 'Year': 2025, 'Semester': 'Fall'},
    ]))

    df = read_progress_report(content, 'progress.xlsx')

    assert df.loc[0, 'MAJOR'] == 'Engineering'


def test_progress_report_wide_format_preserves_major():
    content = _xlsx_bytes(pd.DataFrame([
        {'ID': '1', 'NAME': 'Alice', 'MAJOR': 'Engineering', 'COURSE_1': 'PBHL201/Fall-2025/A'},
    ]))

    df = read_progress_report(content, 'progress.xlsx')

    assert df.loc[0, 'MAJOR'] == 'Engineering'


def test_process_progress_report_carries_major_to_pivots():
    df = pd.DataFrame([
        {'ID': '1', 'NAME': 'Alice', 'MAJOR': 'Engineering', 'Course': 'PBHL201', 'Grade': 'A', 'Year': 2025, 'Semester': 'Fall'},
    ])

    req_df, int_df, _extra_df, _extra_list = process_progress_report(
        df,
        target_courses={'PBHL201': 3},
        intensive_courses={'ARAB101': 3},
        target_rules={'PBHL201': [{'Credits': 3, 'PassingGrades': 'A,B,C,CR', 'FromOrd': -1e9, 'ToOrd': 1e9}]},
        intensive_rules={'ARAB101': [{'Credits': 3, 'PassingGrades': 'A,B,C,CR', 'FromOrd': -1e9, 'ToOrd': 1e9}]},
    )

    assert req_df.loc[0, 'MAJOR'] == 'Engineering'
    assert int_df.loc[0, 'MAJOR'] == 'Engineering'


def test_push_progress_to_advising_preserves_major(tmp_path: Path, monkeypatch):
    monkeypatch.setenv('LOCAL_STORAGE_PATH', str(tmp_path / 'storage'))
    get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    session = Session()
    try:
        major = Major(code='TEST', name='Test Major')
        session.add(major)
        session.flush()
        session.add(
            DatasetVersion(
                major_id=major.id,
                dataset_type='course_config',
                version_label='config',
                is_active=True,
                parsed_payload={'records': [{
                    'target_courses': {'PBHL201': 3},
                    'intensive_courses': {},
                    'target_rules': {'PBHL201': [{'Credits': 3, 'PassingGrades': 'A,B,C,CR', 'FromOrd': -1e9, 'ToOrd': 1e9}]},
                    'intensive_rules': {},
                }]},
                metadata_json={},
            )
        )
        session.add(
            DatasetVersion(
                major_id=major.id,
                dataset_type='progress_report',
                version_label='progress',
                is_active=True,
                parsed_payload={'records': [{
                    'ID': '1',
                    'NAME': 'Alice',
                    'MAJOR': 'Engineering',
                    'Course': 'PBHL201',
                    'Grade': 'A',
                    'Year': 2025,
                    'Semester': 'Fall',
                }]},
                metadata_json={},
            )
        )
        session.commit()

        push_progress_to_advising(session, 'TEST', user_id=None)
        pushed = get_active_dataset(session, 'TEST', 'progress')
        assert pushed is not None
        records = pushed.parsed_payload['records']
        assert records[0]['MAJOR'] == 'Engineering'
    finally:
        session.close()
        get_settings.cache_clear()


def test_generate_report_returns_per_student_extra_courses(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    session = Session()
    try:
        major = Major(code='TEST', name='Test Major')
        session.add(major)
        session.flush()
        session.add(
            DatasetVersion(
                major_id=major.id,
                dataset_type='course_config',
                version_label='config',
                is_active=True,
                parsed_payload={'records': [{
                    'target_courses': {'PBHL201': 3},
                    'intensive_courses': {},
                    'target_rules': {'PBHL201': [{'Credits': 3, 'PassingGrades': 'A,B,C,CR', 'FromOrd': -1e9, 'ToOrd': 1e9}]},
                    'intensive_rules': {},
                }]},
                metadata_json={},
            )
        )
        session.add(
            DatasetVersion(
                major_id=major.id,
                dataset_type='progress_report',
                version_label='progress',
                is_active=True,
                parsed_payload={'records': [
                    {'ID': '1', 'NAME': 'Alice', 'Course': 'PBHL201', 'Grade': 'A', 'Year': 2025, 'Semester': 'Fall'},
                    {'ID': '1', 'NAME': 'Alice', 'Course': 'PBHL450', 'Grade': 'A', 'Year': 2025, 'Semester': 'Fall'},
                    {'ID': '2', 'NAME': 'Bob', 'Course': 'PBHL201', 'Grade': 'A', 'Year': 2025, 'Semester': 'Fall'},
                ]},
                metadata_json={},
            )
        )
        session.commit()

        report = generate_report(session, 'TEST', page_size=50)
        by_student = {row.student_id: row for row in report.required}

        assert report.extra_courses == ['PBHL450']
        assert by_student['1'].extra_courses == ['PBHL450']
        assert by_student['2'].extra_courses == []
    finally:
        session.close()


def test_generate_report_removes_assigned_extra_courses(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    session = Session()
    try:
        major = Major(code='TEST', name='Test Major')
        session.add(major)
        session.flush()
        session.add(
            DatasetVersion(
                major_id=major.id,
                dataset_type='course_config',
                version_label='config',
                is_active=True,
                parsed_payload={'records': [{
                    'target_courses': {'PBHL201': 3},
                    'intensive_courses': {},
                    'target_rules': {'PBHL201': [{'Credits': 3, 'PassingGrades': 'A,B,C,CR', 'FromOrd': -1e9, 'ToOrd': 1e9}]},
                    'intensive_rules': {},
                }]},
                metadata_json={},
            )
        )
        session.add(
            DatasetVersion(
                major_id=major.id,
                dataset_type='progress_report',
                version_label='progress',
                is_active=True,
                parsed_payload={'records': [
                    {'ID': '1', 'NAME': 'Alice', 'Course': 'PBHL201', 'Grade': 'A', 'Year': 2025, 'Semester': 'Fall'},
                    {'ID': '1', 'NAME': 'Alice', 'Course': 'PBHL450', 'Grade': 'A', 'Year': 2025, 'Semester': 'Fall'},
                ]},
                metadata_json={},
            )
        )
        session.add(AssignmentType(major_id=major.id, label='SCE', sort_order=0))
        session.add(ProgressAssignment(major_id=major.id, student_id='1', assignment_type='SCE', course_code='PBHL450'))
        session.commit()

        report = generate_report(session, 'TEST', page_size=50)
        assert report.extra_courses == []
        assert report.required[0].extra_courses == []
    finally:
        session.close()


def test_generate_report_recovers_major_from_stored_file_when_payload_is_legacy(tmp_path: Path, monkeypatch):
    monkeypatch.setenv('LOCAL_STORAGE_PATH', str(tmp_path / 'storage'))
    get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    content = _xlsx_bytes(pd.DataFrame([
        {'ID': '1', 'NAME': 'Alice', 'MAJOR': 'Engineering', 'Course': 'PBHL201', 'Grade': 'A', 'Year': 2025, 'Semester': 'Fall'},
    ]))
    storage_key = 'datasets/TEST/progress_report/source.xlsx'
    StorageService().put_bytes(storage_key, content)

    session = Session()
    try:
        major = Major(code='TEST', name='Test Major')
        session.add(major)
        session.flush()
        session.add(
            DatasetVersion(
                major_id=major.id,
                dataset_type='course_config',
                version_label='config',
                is_active=True,
                parsed_payload={'records': [{
                    'target_courses': {'PBHL201': 3},
                    'intensive_courses': {},
                    'target_rules': {'PBHL201': [{'Credits': 3, 'PassingGrades': 'A,B,C,CR', 'FromOrd': -1e9, 'ToOrd': 1e9}]},
                    'intensive_rules': {},
                }]},
                metadata_json={},
            )
        )
        session.add(
            DatasetVersion(
                major_id=major.id,
                dataset_type='progress_report',
                version_label='legacy',
                original_filename='source.xlsx',
                storage_key=storage_key,
                is_active=True,
                parsed_payload={'records': [
                    {'ID': '1', 'NAME': 'Alice', 'Course': 'PBHL201', 'Grade': 'A', 'Year': 2025, 'Semester': 'Fall'},
                ]},
                metadata_json={},
            )
        )
        session.commit()

        report = generate_report(session, 'TEST', page_size=50)
        assert report.required[0].major == 'Engineering'
    finally:
        session.close()
        get_settings.cache_clear()
