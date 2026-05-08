from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel


class ApiError(BaseModel):
    error: str
    detail: str = ""
    code: str = ""


def bad_request(
    error: str, detail: str = "", code: str = "bad_request"
) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=ApiError(error=error, detail=detail, code=code).model_dump(),
    )


def unauthorized(error: str = "未授权", detail: str = "") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=ApiError(error=error, detail=detail, code="unauthorized").model_dump(),
    )


def forbidden(error: str = "需要管理员权限", detail: str = "") -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=ApiError(error=error, detail=detail, code="forbidden").model_dump(),
    )


def not_found(error: str = "资源不存在", detail: str = "") -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=ApiError(error=error, detail=detail, code="not_found").model_dump(),
    )
