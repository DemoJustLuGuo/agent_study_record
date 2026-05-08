from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import chat, knowledge, rag, settings, traces


def _cors_origins() -> list[str]:
    raw = (os.environ.get("APP_CORS_ORIGINS") or "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    return [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(
        title="通信智能体后端 API",
        version="0.14.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/version")
    def version():
        return {"version": app.version}

    app.include_router(chat.create_router())
    app.include_router(rag.create_router())
    app.include_router(knowledge.create_router())
    app.include_router(settings.create_router())
    app.include_router(traces.create_router())
    return app
