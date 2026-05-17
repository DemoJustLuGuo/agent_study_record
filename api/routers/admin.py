from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_admin_token_service, require_admin
from api.schemas import (
    AdminSessionResponse,
    AdminTokenUpdateRequest,
    AdminTokenUpdateResponse,
)
from services.admin_token_service import AdminTokenService


def create_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

    @router.get(
        "/session",
        response_model=AdminSessionResponse,
        dependencies=[Depends(require_admin)],
    )
    def get_session() -> dict[str, bool | str]:
        return {"ok": True, "role": "admin"}

    @router.put(
        "/token",
        response_model=AdminTokenUpdateResponse,
        dependencies=[Depends(require_admin)],
    )
    def update_token(
        body: AdminTokenUpdateRequest,
        service: AdminTokenService = Depends(get_admin_token_service),
    ) -> dict[str, object]:
        return service.update_token(body.new_token)

    return router
