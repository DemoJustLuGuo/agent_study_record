from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class HealthResponse(BaseModel):
    ok: bool


class VersionResponse(BaseModel):
    version: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ThreadSummary(ResponseModel):
    thread_id: str
    title: str = ""
    renamed: bool = False
    auto_named: bool = False
    updated_at: str = ""


class ThreadListResponse(BaseModel):
    items: list[ThreadSummary]
    current_thread_id: str


class ThreadStateResponse(BaseModel):
    thread_id: str
    history: list[ChatMessage] = Field(default_factory=list)
    status: str = ""


class ThreadOperationResponse(ResponseModel):
    thread_id: str = ""
    threads: list[ThreadSummary] = Field(default_factory=list)
    choices: list[tuple[str, str]] = Field(default_factory=list)
    history: list[ChatMessage] = Field(default_factory=list)
    status: str = ""
    ok: bool | None = None


class RagReference(ResponseModel):
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagQueryResponse(ResponseModel):
    query: str = ""
    answer: str = ""
    references: list[RagReference] = Field(default_factory=list)
    retrieval_debug: dict[str, Any] = Field(default_factory=dict)
    rerank_debug: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class KnowledgeActionDetail(ResponseModel):
    url: str = ""
    status: str = ""
    reason: str = ""
    cleaning: dict[str, Any] = Field(default_factory=dict)


class KnowledgeActionResponse(ResponseModel):
    result: str | None = None
    snapshot: str | None = None
    error: str | None = None
    total: int | None = None
    added: int | None = None
    updated: int | None = None
    skipped: int | None = None
    failed: int | None = None
    details: list[KnowledgeActionDetail] = Field(default_factory=list)
    removed_source_count: int | None = None
    removed_sources: list[str] = Field(default_factory=list)


class ConnectionSettingsResponse(BaseModel):
    openai_base_url: str = ""
    api_key_configured: bool = False
    api_key: str = ""
    status: str = ""
    note: str = ""


class SaveConnectionSettingsResponse(BaseModel):
    message: str
    note: str


class TraceListItem(BaseModel):
    trace_id: str
    updated_at: float
    size: int


class TraceListResponse(BaseModel):
    items: list[TraceListItem] = Field(default_factory=list)


class TraceDetailResponse(BaseModel):
    trace_id: str
    events: list[dict[str, Any]] = Field(default_factory=list)
