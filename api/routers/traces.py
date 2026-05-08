from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_trace_service, require_admin
from api.errors import not_found
from services.trace_service import TraceService


def create_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/traces",
        tags=["traces"],
        dependencies=[Depends(require_admin)],
    )

    @router.get("")
    def list_traces(
        limit: int = Query(default=50, ge=1, le=200),
        service: TraceService = Depends(get_trace_service),
    ):
        return {"items": service.list_traces(limit=limit)}

    @router.get("/{trace_id}")
    def get_trace(trace_id: str, service: TraceService = Depends(get_trace_service)):
        try:
            return service.get_trace(trace_id)
        except FileNotFoundError as error:
            raise not_found("trace 不存在") from error

    return router
