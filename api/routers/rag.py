from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_rag_query_service, require_admin
from api.errors import bad_request
from api.schemas import RagMetricsResetResponse, RagMetricsResponse, RagQueryResponse
from rag.metrics import get_rag_metrics_snapshot, reset_rag_metrics
from services.rag_query_service import RagQueryService


class RagQueryRequest(BaseModel):
    query: str = Field(default="", description="RAG 检索问题")


def create_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

    @router.post("/query", response_model=RagQueryResponse)
    def query_rag(
        body: RagQueryRequest,
        service: RagQueryService = Depends(get_rag_query_service),
    ):
        result = service.answer_with_references(body.query)
        if result.get("error"):
            raise bad_request(str(result.get("error")))
        return result

    @router.get("/metrics", response_model=RagMetricsResponse)
    def get_metrics():
        return get_rag_metrics_snapshot()

    @router.post(
        "/metrics/reset",
        response_model=RagMetricsResetResponse,
        dependencies=[Depends(require_admin)],
    )
    def reset_metrics():
        return {"message": reset_rag_metrics()}

    return router
