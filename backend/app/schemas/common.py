from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str


class PaginationMeta(BaseModel):
    total: int


class AuditEnvelope(BaseModel):
    generated_at: datetime
    items: list[dict[str, Any]]
