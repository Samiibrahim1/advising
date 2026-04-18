from __future__ import annotations

from io import BytesIO

pandas_imported = False
try:
    import pandas as pd
    pandas_imported = True
except ImportError:
    pass

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_major_access, get_db, require_admin, require_staff
from app.models import DatasetVersion, User
from app.schemas.admin import DatasetVersionResponse
from app.services.audit import log_event
from app.services.dataset_service import get_active_dataset, upload_dataset
from app.services.storage import StorageService

_TEMPLATE_COLUMNS: dict[str, dict[str, list[str]]] = {
    'courses': {
        # Column names must match exactly what eligibility_utils.py reads
        # Prerequisite: comma-separated; use " / " between alternatives for OR logic
        # Type values: required | elective | intensive
        # Suggested Semester format: Fall-1, Spring-2, Summer-3, …
        'Courses': ['Course Code', 'Title', 'Credits', 'Type', 'Offered', 'Suggested Semester', 'Prerequisite', 'Concurrent', 'Corequisite'],
    },
    'progress': {
        'Required Courses': ['ID', 'NAME'],
        'Intensive Courses': ['ID', 'NAME'],
    },
    'email_roster': {
        'Email Roster': ['Student ID', 'Student Name', 'Email'],
    },
    'placements': {
        # Bulk intensive-course placement report — one row per student
        # placement_course: the intensive course the student placed INTO (e.g. ARAB201)
        # The system will automatically exclude all lower-level intensive ancestors.
        'Placements': ['student_id', 'placement_course'],
    },
}

_TEMPLATE_SAMPLE_ROWS: dict[str, dict[str, list]] = {
    'courses': {
        'Courses': [
            ['PBHL201', 'Introduction to Public Health', 3, 'required', 'Fall/Spring', 'Fall-1', '', '', ''],
            ['PBHL301', 'Epidemiology', 3, 'required', 'Fall', 'Fall-2', 'PBHL201', '', ''],
            ['PBHL401', 'Health Policy', 3, 'required', 'Spring', 'Spring-3', 'PBHL201, PBHL301', '', ''],
            # OR example: student needs PBHL301 OR PBHL401 (use " / " as the OR separator)
            ['PBHL450', 'Research Methods & Design', 3, 'elective', 'Spring', 'Spring-3', 'PBHL301 / PBHL401', '', ''],
            ['ARAB101', 'Arabic Language I', 3, 'intensive', 'Fall/Spring', 'Fall-1', '', '', ''],
            ['ARAB201', 'Arabic Language II', 3, 'intensive', 'Fall/Spring', 'Fall-2', 'ARAB101', '', ''],
        ],
    },
    'progress': {
        'Required Courses': [
            ['20210001', 'John Doe'],
            ['20210002', 'Jane Smith'],
        ],
        'Intensive Courses': [
            ['20210001', 'John Doe'],
        ],
    },
    'email_roster': {
        'Email Roster': [
            ['20210001', 'John Doe', 'johndoe@university.edu'],
            ['20210002', 'Jane Smith', 'janesmith@university.edu'],
        ],
    },
    'placements': {
        'Placements': [
            ['20210001', 'ARAB201'],
            ['20210002', 'ARAB101'],
        ],
    },
}

router = APIRouter(prefix='/datasets', tags=['datasets'])

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@router.get('/{major_code}', response_model=list[DatasetVersionResponse])
def list_dataset_versions(major_code: str, user: User = Depends(require_staff), db: Session = Depends(get_db)) -> list[DatasetVersion]:
    ensure_major_access(major_code, db, user)
    return list(
        db.scalars(
            select(DatasetVersion).where(DatasetVersion.major.has(code=major_code)).order_by(DatasetVersion.created_at.desc())
        )
    )


@router.get('/templates/{dataset_type}')
def download_template(dataset_type: str, user: User = Depends(require_staff)) -> Response:
    """Download a blank XLSX template for the given dataset type."""
    sheets = _TEMPLATE_COLUMNS.get(dataset_type)
    if not sheets:
        raise HTTPException(status_code=400, detail=f'No template available for dataset type: {dataset_type}')
    import pandas as pd
    buf = BytesIO()
    sample_rows = _TEMPLATE_SAMPLE_ROWS.get(dataset_type, {})
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        for sheet_name, columns in sheets.items():
            rows = sample_rows.get(sheet_name, [])
            pd.DataFrame(rows, columns=columns).to_excel(writer, sheet_name=sheet_name, index=False)
    buf.seek(0)
    filename = f'{dataset_type}_template.xlsx'
    return Response(
        content=buf.read(),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.get('/{major_code}/{dataset_type}/download')
def download_current_file(major_code: str, dataset_type: str, user: User = Depends(require_staff), db: Session = Depends(get_db)) -> StreamingResponse:
    """Download the currently active uploaded file for a dataset type."""
    ensure_major_access(major_code, db, user)
    version = get_active_dataset(db, major_code, dataset_type)
    if not version:
        raise HTTPException(status_code=404, detail='No active file for this dataset type.')
    storage = StorageService()
    try:
        content = storage.get_bytes(version.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='File no longer available. Please re-upload the dataset.')
    filename = version.original_filename or f'{dataset_type}.xlsx'
    media_type = 'text/csv' if filename.lower().endswith('.csv') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.delete('/{version_id}', status_code=204)
def delete_dataset_version(version_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    version = db.get(DatasetVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail='Dataset version not found.')
    if version.is_active:
        raise HTTPException(status_code=400, detail='Cannot delete the active version. Activate another version first.')
    log_event(db, user.id, 'dataset.deleted', 'dataset_version', str(version_id), {'dataset_type': version.dataset_type})
    db.delete(version)
    db.commit()


@router.post('/{version_id}/activate', response_model=DatasetVersionResponse)
def activate_dataset_version(version_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from sqlalchemy import update
    version = db.get(DatasetVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail='Dataset version not found.')
    # Deactivate all versions of same type for same major
    db.execute(
        update(DatasetVersion)
        .where(DatasetVersion.major_id == version.major_id, DatasetVersion.dataset_type == version.dataset_type)
        .values(is_active=False)
    )
    version.is_active = True
    log_event(db, user.id, 'dataset.activated', 'dataset_version', str(version_id), {'dataset_type': version.dataset_type})
    db.commit()
    db.refresh(version)
    return version


@router.post('/upload', response_model=DatasetVersionResponse)
async def upload_dataset_route(
    major_code: str = Form(...),
    dataset_type: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
) -> DatasetVersion:
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f'File too large. Maximum upload size is {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB.')
    try:
        version = upload_dataset(
            db,
            major_code=major_code,
            dataset_type=dataset_type,
            filename=file.filename,
            content=content,
            user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Store uploader info in metadata so it surfaces in the version list
    version.metadata_json = {**version.metadata_json, 'uploaded_by': user.full_name or user.email}
    log_event(db, user.id, 'dataset.uploaded', 'dataset_version', str(version.id), {'major_code': major_code, 'dataset_type': dataset_type})
    db.commit()
    db.refresh(version)
    return version
