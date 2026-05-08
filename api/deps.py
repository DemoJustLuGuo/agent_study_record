from __future__ import annotations

import os
from threading import Lock
from typing import Annotated

from fastapi import Header

from api.errors import forbidden, unauthorized
from services.chat_service import ChatService
from services.knowledge_service import KnowledgeService
from services.rag_query_service import RagQueryService
from services.trace_service import TraceService

_chat_service: ChatService | None = None
_chat_service_lock = Lock()
_knowledge_service: KnowledgeService | None = None
_knowledge_service_lock = Lock()
_rag_query_service: RagQueryService | None = None
_rag_query_service_lock = Lock()
_trace_service: TraceService | None = None
_trace_service_lock = Lock()


def _extract_bearer(authorization: str | None) -> str:
    scheme, _, value = str(authorization or "").partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return value.strip()


def require_admin(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    expected = (os.environ.get("APP_ADMIN_TOKEN") or "").strip()
    if not expected:
        raise unauthorized(
            "未配置管理 Token",
            "请在运行环境设置 APP_ADMIN_TOKEN 后再调用管理 API。",
        )
    token = _extract_bearer(authorization)
    if not token:
        raise unauthorized("缺少管理 Token")
    if token != expected:
        raise forbidden("管理 Token 无效")
    return {"role": "admin"}


def get_chat_service() -> ChatService:
    global _chat_service
    with _chat_service_lock:
        if _chat_service is None:
            _chat_service = ChatService()
        return _chat_service


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    with _knowledge_service_lock:
        if _knowledge_service is None:
            _knowledge_service = KnowledgeService()
        return _knowledge_service


def get_rag_query_service() -> RagQueryService:
    global _rag_query_service
    with _rag_query_service_lock:
        if _rag_query_service is None:
            _rag_query_service = RagQueryService()
        return _rag_query_service


def get_trace_service() -> TraceService:
    global _trace_service
    with _trace_service_lock:
        if _trace_service is None:
            _trace_service = TraceService()
        return _trace_service
