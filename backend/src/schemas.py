"""Pydantic request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl

from src.models import MessageIntent, MessageMode, MessageRole, MessageScope, ResourceStatus, UserRole


# --- Auth ---


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Technologies ---


class TechnologyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class TechnologyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class TechnologyOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    ready_resource_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Resources ---


class ResourceCreateBatch(BaseModel):
    urls: list[HttpUrl] = Field(min_length=1, max_length=50)


class ResourceOut(BaseModel):
    id: int
    technology_id: int
    url: str
    title: str | None
    status: ResourceStatus
    error: str | None
    chunk_count: int
    last_ingested_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResourceBatchResult(BaseModel):
    created: list[ResourceOut]
    skipped: list[dict]  # [{"url": ..., "reason": "duplicate"}]


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=8, ge=1, le=20)


class RetrievalHit(BaseModel):
    chunk_id: str
    resource_id: int
    title: str | None
    url: str | None
    heading_path: str | None
    content: str
    score: float


# --- Conversations & messages ---


class ConversationCreate(BaseModel):
    technology_id: int


class ConversationOut(BaseModel):
    id: str
    technology_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceOut(BaseModel):
    n: int
    chunk_id: str
    resource_id: int
    url: str | None
    title: str | None
    heading_path: str | None
    score: float
    cited: bool


class MessageOut(BaseModel):
    id: str
    role: MessageRole
    content: str
    scope: MessageScope | None
    intent: MessageIntent | None
    mode: MessageMode | None
    sources: list[SourceOut] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
