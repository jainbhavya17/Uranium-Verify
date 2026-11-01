from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Meta(BaseModel):
    request_id: str
    source_version: str = "phase-2"
    processed_at: int
    page: int | None = None
    page_size: int | None = None
    total: int | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    field_errors: dict[str, str] = Field(default_factory=dict)
    retryable: bool = False


class Envelope(BaseModel, Generic[T]):
    data: T | None = None
    meta: Meta
    error: ErrorDetail | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class UserView(BaseModel):
    id: str
    email: str
    name: str
    roles: list[str]
    institution_ids: list[str]
    landing: str
    expires_at: int
    csrf_token: str | None = None
    mode: str = "DEMO"


class ApplicationView(BaseModel):
    id: str
    institution_id: str
    institution_name: str
    category: str
    academic_year: str
    status: str
    is_mock: bool
    version: int = 1
    updated_at: int = 0
    catalogue_id: str | None = None
    revision_id: str | None = None


class InstitutionView(BaseModel):
    id: str
    name: str
    permanent_id: str
    is_mock: bool


class EvidenceView(BaseModel):
    id: str
    document_id: str
    revision_id: str
    number: int
    original_name: str
    media_type: str
    sha256: str
    status: str
    is_mock: bool


class PreviewView(BaseModel):
    url: str
    expires_at: int


class HealthView(BaseModel):
    status: str
    database: str
    storage: str
    mode: str = "DEMO"


class JobState(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobView(BaseModel):
    id: str
    state: JobState
    revision_id: str
    progress: int | None = Field(default=None, ge=0, le=100)
    error: ErrorDetail | None = None
