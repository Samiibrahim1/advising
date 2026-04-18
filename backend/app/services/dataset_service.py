from __future__ import annotations

import hashlib
import json
from io import BytesIO
from typing import Any, Optional

import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import AdvisingPeriod, DatasetVersion, EmailRosterEntry, Major, UploadBatch
from app.services.storage import StorageService


# Map dataset_type → the AdvisingPeriod column that tracks its snapshot
_SNAPSHOT_COLUMN = {
    'progress_report': 'progress_version_id',
    'progress': 'progress_dataset_version_id',
    'course_config': 'config_version_id',
}


def _link_to_active_period(session: Session, major_id: int, dataset_type: str, version_id: int) -> None:
    """Update the active period's snapshot pointer so it tracks the latest upload."""
    col_name = _SNAPSHOT_COLUMN.get(dataset_type)
    if not col_name:
        return
    active_period = session.scalar(
        select(AdvisingPeriod).where(
            AdvisingPeriod.major_id == major_id,
            AdvisingPeriod.is_active.is_(True),
        )
    )
    if active_period:
        setattr(active_period, col_name, version_id)

DATASET_TYPES = {'courses', 'progress', 'advising_selections', 'email_roster', 'progress_report', 'course_config', 'placements'}


def _json_safe_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    safe_df = df.where(pd.notnull(df), None)
    return json.loads(safe_df.to_json(orient='records', date_format='iso'))


def load_progress_excel(content: bytes | BytesIO | str) -> pd.DataFrame:
    io_obj = BytesIO(content) if isinstance(content, (bytes, bytearray)) else content
    sheets = pd.read_excel(io_obj, sheet_name=None)
    req_key = next((key for key in sheets.keys() if 'required' in key.lower()), None)
    int_key = next((key for key in sheets.keys() if 'intensive' in key.lower()), None)
    if req_key is None:
        req_key = list(sheets.keys())[0]
    req_df = sheets[req_key].copy()
    if int_key is None:
        return req_df

    int_df = sheets[int_key].copy()
    base_columns = ['ID', 'NAME']
    numeric_columns = ['# of Credits Completed', '# Registered', '# Remaining', 'Total Credits', 'GPA']
    for column in base_columns:
        if column not in req_df.columns:
            req_df[column] = None
        if column not in int_df.columns:
            int_df[column] = None

    def course_columns(df: pd.DataFrame) -> list[str]:
        return [column for column in df.columns if column not in base_columns + numeric_columns]

    req_courses = course_columns(req_df)
    int_courses = course_columns(int_df)
    merged = pd.merge(
        req_df[base_columns + req_courses + [column for column in numeric_columns if column in req_df.columns]],
        int_df[base_columns + int_courses + [column for column in numeric_columns if column in int_df.columns]],
        on=base_columns,
        how='outer',
        suffixes=('_req', '_int'),
    )
    for column in numeric_columns:
        req_col = f'{column}_req'
        int_col = f'{column}_int'
        if req_col in merged.columns and int_col in merged.columns:
            merged[column] = merged[req_col].combine_first(merged[int_col])
            merged.drop(columns=[req_col, int_col], inplace=True)
        elif req_col in merged.columns:
            merged[column] = merged.pop(req_col)
        elif int_col in merged.columns:
            merged[column] = merged.pop(int_col)
    return merged


def _parse_dataset(dataset_type: str, file_bytes: bytes, filename: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if dataset_type == 'courses':
        df = pd.read_excel(BytesIO(file_bytes))
        return _json_safe_records(df), {'rows': len(df), 'columns': list(map(str, df.columns))}
    if dataset_type == 'progress':
        df = load_progress_excel(file_bytes)
        return _json_safe_records(df), {'rows': len(df), 'columns': list(map(str, df.columns))}
    if dataset_type == 'advising_selections':
        df = pd.read_csv(BytesIO(file_bytes)) if filename.lower().endswith('.csv') else pd.read_excel(BytesIO(file_bytes))
        return _json_safe_records(df), {'rows': len(df), 'columns': list(map(str, df.columns))}
    if dataset_type == 'email_roster':
        if filename.lower().endswith('.json'):
            payload = json.loads(file_bytes.decode('utf-8'))
            rows = [
                {'Student ID': str(student_id), 'Email': str(email).strip().lower()}
                for student_id, email in payload.items()
                if student_id and email
            ]
            return rows, {'rows': len(rows), 'columns': ['Student ID', 'Email']}
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(BytesIO(file_bytes))
        else:
            df = pd.read_excel(BytesIO(file_bytes))
        return _json_safe_records(df), {'rows': len(df), 'columns': list(map(str, df.columns))}
    if dataset_type == 'progress_report':
        from app.services.progress_processing import read_progress_report  # late import avoids circular
        df = read_progress_report(file_bytes, filename)
        records = _json_safe_records(df)
        return records, {'rows': len(df), 'student_count': int(df['ID'].nunique())}
    if dataset_type == 'course_config':
        from app.services.progress_processing import read_course_config  # late import avoids circular
        config = read_course_config(file_bytes, filename)
        # Store the config dict as a single-element records list so the standard
        # DatasetVersion.parsed_payload['records'] access pattern still works.
        return [config], {'type': 'course_config', 'required_count': len(config.get('target_courses', {})), 'intensive_count': len(config.get('intensive_courses', {}))}
    if dataset_type == 'placements':
        try:
            df = pd.read_excel(BytesIO(file_bytes)) if not filename.lower().endswith('.csv') else pd.read_csv(BytesIO(file_bytes))
        except Exception:
            df = pd.read_csv(BytesIO(file_bytes))
        return _json_safe_records(df), {'rows': len(df)}
    raise ValueError(f'Unsupported dataset type: {dataset_type}')


def _major_or_404(session: Session, major_code: str) -> Major:
    major = session.scalar(select(Major).where(Major.code == major_code))
    if not major:
        raise ValueError(f'Unknown major: {major_code}')
    return major


def upload_dataset(session: Session, *, major_code: str, dataset_type: str, filename: str, content: bytes, user_id: Optional[int]) -> DatasetVersion:
    if dataset_type not in DATASET_TYPES:
        raise ValueError(f'Unsupported dataset type: {dataset_type}')

    major = _major_or_404(session, major_code)
    storage = StorageService()
    parsed_payload, metadata = _parse_dataset(dataset_type, content, filename)
    checksum = hashlib.sha256(content).hexdigest()
    key = f'datasets/{major.code}/{dataset_type}/{checksum}-{filename}'
    storage.put_bytes(key, content)

    session.execute(
        update(DatasetVersion)
        .where(DatasetVersion.major_id == major.id, DatasetVersion.dataset_type == dataset_type)
        .values(is_active=False)
    )

    version = DatasetVersion(
        major_id=major.id,
        dataset_type=dataset_type,
        version_label=checksum[:12],
        storage_key=key,
        original_filename=filename,
        checksum=checksum,
        is_active=True,
        parsed_payload={'records': parsed_payload},
        metadata_json=metadata,
    )
    session.add(version)
    session.flush()

    batch = UploadBatch(
        major_id=major.id,
        uploaded_by_user_id=user_id,
        status='processed',
        manifest={'dataset_type': dataset_type, 'dataset_version_id': version.id, 'filename': filename},
    )
    session.add(batch)

    if dataset_type == 'email_roster':
        _refresh_email_roster(session, major.id, parsed_payload)

    _link_to_active_period(session, major.id, dataset_type, version.id)

    session.commit()
    session.refresh(version)
    return version


def _refresh_email_roster(session: Session, major_id: int, rows: list[dict[str, Any]]) -> None:
    session.query(EmailRosterEntry).filter(EmailRosterEntry.major_id == major_id).delete()
    for row in rows:
        student_id = str(row.get('Student ID') or row.get('ID') or row.get('student_id') or '').strip()
        email = str(row.get('Email') or row.get('email') or '').strip().lower()
        if not student_id or not email:
            continue
        session.add(
            EmailRosterEntry(
                major_id=major_id,
                student_id=student_id,
                student_name=str(row.get('Student Name') or row.get('NAME') or row.get('name') or '').strip() or None,
                email=email,
            )
        )


def get_active_dataset(session: Session, major_code: str, dataset_type: str) -> Optional[DatasetVersion]:
    major = _major_or_404(session, major_code)
    return session.scalar(
        select(DatasetVersion)
        .where(DatasetVersion.major_id == major.id, DatasetVersion.dataset_type == dataset_type, DatasetVersion.is_active.is_(True))
        .order_by(DatasetVersion.created_at.desc())
    )


def get_dataset_records(session: Session, major_code: str, dataset_type: str) -> list[dict[str, Any]]:
    dataset = get_active_dataset(session, major_code, dataset_type)
    if not dataset:
        return []
    return dataset.parsed_payload.get('records', [])


def dataset_dataframe(session: Session, major_code: str, dataset_type: str) -> pd.DataFrame:
    records = get_dataset_records(session, major_code, dataset_type)
    return pd.DataFrame(records)
