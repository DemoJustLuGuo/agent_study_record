from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi import File, Form, UploadFile
from pydantic import BaseModel, Field

from api.deps import get_knowledge_service, require_admin
from api.errors import bad_request
from api.schemas import KnowledgeActionResponse, KnowledgeUploadPolicyResponse
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


def _safe_upload_filename(upload: UploadFile) -> str:
    return Path(upload.filename or "upload").name


def _upload_result_payload(
    result_text: str,
    filename: str,
    source_type: str,
) -> dict[str, object]:
    result = (result_text or "").strip()
    payload: dict[str, object] = {
        "filename": filename,
        "source_type": source_type,
    }
    if result.startswith("✅"):
        payload["result"] = result
    else:
        payload["error"] = result or "文件上传失败。"
    return payload


def create_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/knowledge",
        tags=["knowledge"],
        dependencies=[Depends(require_admin)],
    )

    @router.post("/web-ingest", response_model=KnowledgeActionResponse)
    def ingest_web_urls(
        body: WebIngestRequest,
        service: KnowledgeService = Depends(get_knowledge_service),
    ):
        return _raise_if_error(service.ingest_web_urls(body.urls, body.operator))

    @router.get("/upload-policy", response_model=KnowledgeUploadPolicyResponse)
    def get_upload_policy(service: KnowledgeService = Depends(get_knowledge_service)):
        return {
            "allowed_extensions": list(service.allowed_upload_extensions()),
            "fully_supported_extensions": [".txt"],
        }

    @router.post("/upload", response_model=KnowledgeActionResponse)
    async def upload_file(
        file: UploadFile = File(...),
        operator: str = Form(default="web-console"),
        service: KnowledgeService = Depends(get_knowledge_service),
    ):
        filename = _safe_upload_filename(file)
        source_type = Path(filename).suffix.lower()
        if not filename or filename == "upload":
            raise bad_request("文件名为空。")

        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=source_type) as tmp:
                temp_path = tmp.name
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    tmp.write(chunk)
            result = service.upload_file(temp_path, operator=operator)
            return _raise_if_error(
                _upload_result_payload(result, filename, source_type)
            )
        finally:
            await file.close()
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    @router.post("/sync", response_model=KnowledgeActionResponse)
    def sync_knowledge(service: KnowledgeService = Depends(get_knowledge_service)):
        return _raise_if_error(service.sync_removed_sources())

    @router.post("/snapshot", response_model=KnowledgeActionResponse)
    def create_snapshot(
        body: SnapshotRequest,
        service: KnowledgeService = Depends(get_knowledge_service),
    ):
        return _raise_if_error(service.create_snapshot(body.tag))

    @router.post("/rollback", response_model=KnowledgeActionResponse)
    def rollback_snapshot(
        body: RollbackRequest,
        service: KnowledgeService = Depends(get_knowledge_service),
    ):
        return _raise_if_error(
            service.rollback_snapshot(body.snapshot_name, body.confirm_name)
        )

    return router
