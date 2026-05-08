from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_rag_query_service
from api.errors import bad_request
from services.rag_query_service import RagQueryService


class RagQueryRequest(BaseModel):
    query: str = Field(default="", description="RAG 检索问题")


def create_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

    @router.post("/query")
    def query_rag(
        body: RagQueryRequest,
        service: RagQueryService = Depends(get_rag_query_service),
    ):
        result = service.answer_with_references(body.query)
        if result.get("error"):
            raise bad_request(str(result.get("error")))
        return result

    return router
