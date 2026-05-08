from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import require_admin
from services.settings_service import (
    load_connection_defaults,
    save_connection_settings,
)


class ConnectionSettingsRequest(BaseModel):
    openai_base_url: str = Field(default="")
    openai_api_key: str = Field(default="")


def create_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/settings",
        tags=["settings"],
        dependencies=[Depends(require_admin)],
    )

    @router.get("/connection")
    def get_connection_settings():
        base_url, _api_key, status = load_connection_defaults()
        return {
            "openai_base_url": base_url,
            "api_key_configured": bool(_api_key),
            "api_key": "",
            "status": status,
            "note": "真实 API Key 不会通过 API 返回；直接保存真实密钥只影响当前进程环境。",
        }

    @router.post("/connection")
    def save_connection_settings_endpoint(body: ConnectionSettingsRequest):
        message = save_connection_settings(body.openai_base_url, body.openai_api_key)
        return {
            "message": message,
            "note": "真实 API Key 写入 os.environ 时只影响当前后端进程；多 worker 部署需在进程启动环境中配置。",
        }

    return router
