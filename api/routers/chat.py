from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_chat_service
from api.errors import bad_request
from services.chat_service import ChatEvent, ChatService

try:
    from sse_starlette.sse import EventSourceResponse
except Exception:  # pragma: no cover
    EventSourceResponse = None


class ChatMessageRequest(BaseModel):
    message: str = Field(default="", description="用户输入")


class RenameThreadRequest(BaseModel):
    title: str = Field(default="", description="新会话标题")


def _next_event(iterator: Iterator[ChatEvent]) -> ChatEvent | None:
    return next(iterator, None)


def create_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

    @router.get("/threads")
    def list_threads(service: ChatService = Depends(get_chat_service)):
        state = service.get_initial_state_data()
        return {
            "items": state["threads"],
            "current_thread_id": state["thread_id"],
        }

    @router.post("/threads")
    def create_thread(service: ChatService = Depends(get_chat_service)):
        return service.create_thread()

    @router.get("/threads/{thread_id}")
    def get_thread(thread_id: str, service: ChatService = Depends(get_chat_service)):
        result = service.switch_thread(thread_id)
        return {
            "thread_id": result["thread_id"],
            "history": result["history"],
            "status": result["status"],
        }

    @router.post("/threads/{thread_id}/rename")
    def rename_thread(
        thread_id: str,
        body: RenameThreadRequest,
        service: ChatService = Depends(get_chat_service),
    ):
        result = service.rename_thread(thread_id, body.title)
        if not result.get("ok"):
            raise bad_request(str(result.get("status") or "重命名失败"))
        return result

    @router.delete("/threads/{thread_id}")
    def close_thread(thread_id: str, service: ChatService = Depends(get_chat_service)):
        return service.close_thread(thread_id)

    @router.post("/{thread_id}/stream")
    async def stream_chat(
        thread_id: str,
        body: ChatMessageRequest,
        service: ChatService = Depends(get_chat_service),
    ):
        if EventSourceResponse is None:  # pragma: no cover
            raise RuntimeError("sse-starlette is not installed")

        iterator = service.stream_reply(thread_id, body.message)
        executor = ThreadPoolExecutor(max_workers=1)

        async def event_generator():
            loop = asyncio.get_running_loop()
            try:
                while True:
                    event = await loop.run_in_executor(executor, _next_event, iterator)
                    if event is None:
                        break
                    yield {
                        "event": event.type,
                        "data": json.dumps(event.data, ensure_ascii=False),
                    }
            finally:
                executor.shutdown(wait=False)

        return EventSourceResponse(event_generator(), ping=15)

    return router
