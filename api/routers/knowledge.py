from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_knowledge_service, require_admin
from api.errors import bad_request
from services.knowledge_service import KnowledgeService


class WebIngestRequest(BaseModel):
    urls: str = Field(default="", description="待入库 URL，支持换行或逗号分隔")
    operator: str = Field(default="api", description="操作人标识")


class SnapshotRequest(BaseModel):
    tag: str = ""


class RollbackRequest(BaseModel):
    snapshot_name: str = ""
    confirm_name: str = ""


def _raise_if_error(result: dict[str, object]) -> dict[str, object]:
    if result.get("error"):
        raise bad_request(str(result.get("error")))
    return result


def create_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/knowledge",
        tags=["knowledge"],
        dependencies=[Depends(require_admin)],
    )

    @router.post("/web-ingest")
    def ingest_web_urls(
        body: WebIngestRequest,
        service: KnowledgeService = Depends(get_knowledge_service),
    ):
        return _raise_if_error(service.ingest_web_urls(body.urls, body.operator))

    @router.post("/sync")
    def sync_knowledge(service: KnowledgeService = Depends(get_knowledge_service)):
        return _raise_if_error(service.sync_removed_sources())

    @router.post("/snapshot")
    def create_snapshot(
        body: SnapshotRequest,
        service: KnowledgeService = Depends(get_knowledge_service),
    ):
        return _raise_if_error(service.create_snapshot(body.tag))

    @router.post("/rollback")
    def rollback_snapshot(
        body: RollbackRequest,
        service: KnowledgeService = Depends(get_knowledge_service),
    ):
        return _raise_if_error(
            service.rollback_snapshot(body.snapshot_name, body.confirm_name)
        )

    return router
