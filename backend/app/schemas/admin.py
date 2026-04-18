from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, computed_field, field_validator, model_validator

from app.schemas.common import ORMModel

_MIN_PASSWORD_LENGTH = 8


def _validate_password_strength(v: str) -> str:
    if len(v) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f'Password must be at least {_MIN_PASSWORD_LENGTH} characters')
    if not any(c.isdigit() for c in v):
        raise ValueError('Password must contain at least one digit')
    if not any(c.isalpha() for c in v):
        raise ValueError('Password must contain at least one letter')
    return v


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str
    major_codes: list[str] = []

    @field_validator('password')
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    major_codes: Optional[list[str]] = None
    new_password: Optional[str] = None

    @field_validator('new_password')
    @classmethod
    def check_new_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return _validate_password_strength(v)
        return v


class UserResponse(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    major_codes: list[str] = []


class MajorCreateRequest(BaseModel):
    code: str
    name: str


class MajorUpdateRequest(BaseModel):
    name: Optional[str] = None
    smtp_email: Optional[str] = None
    smtp_password: Optional[str] = None


class MajorResponse(ORMModel):
    id: int
    code: str
    name: str
    is_active: bool
    smtp_email: Optional[str] = None
    smtp_configured: bool = False

    @model_validator(mode='before')
    @classmethod
    def _fill_smtp_configured(cls, data: Any) -> Any:
        # Works for both ORM objects and dicts
        if hasattr(data, 'smtp_email'):
            email = data.smtp_email
            pwd = data.smtp_password
        else:
            email = data.get('smtp_email')
            pwd = data.get('smtp_password')
        if isinstance(data, dict):
            data['smtp_configured'] = bool(email and pwd)
        else:
            data.__dict__['smtp_configured'] = bool(email and pwd)
        return data


class PeriodCreateRequest(BaseModel):
    major_code: str
    semester: str
    year: int
    advisor_name: str


class PeriodResponse(ORMModel):
    id: int
    major_id: int
    period_code: str
    semester: str
    year: int
    advisor_name: str
    is_active: bool
    archived_at: Optional[datetime]
    progress_version_id: Optional[int] = None


class DatasetVersionResponse(ORMModel):
    id: int
    major_id: int
    dataset_type: str
    version_label: str
    original_filename: Optional[str]
    is_active: bool
    metadata_json: dict[str, Any]
    created_at: datetime

    @computed_field
    @property
    def uploaded_by(self) -> Optional[str]:
        return self.metadata_json.get('uploaded_by')


class TemplateUpdateRequest(BaseModel):
    major_code: Optional[str] = None
    template_key: str
    display_name: str
    description: str = ''
    subject_template: str
    body_template: str
    include_summary: bool = True


class TemplateResponse(ORMModel):
    id: int
    major_id: Optional[int]
    template_key: str
    display_name: str
    description: str
    subject_template: str
    body_template: str
    include_summary: bool


class BackupRunResponse(ORMModel):
    id: int
    status: str
    storage_key: Optional[str]
    manifest: dict[str, Any]
    notes: Optional[str]
    created_at: datetime


class AuditEventResponse(ORMModel):
    id: int
    actor_user_id: Optional[int]
    actor_name: Optional[str] = None
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    created_at: datetime

    @model_validator(mode='before')
    @classmethod
    def populate_actor(cls, v: Any) -> Any:
        if hasattr(v, 'actor'):
            actor = getattr(v, 'actor', None)
            if actor is not None and hasattr(actor, 'full_name'):
                v.__dict__['actor_name'] = actor.full_name
        return v
