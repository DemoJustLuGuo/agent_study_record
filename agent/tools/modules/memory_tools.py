from threading import Lock
from typing import TYPE_CHECKING

from langchain_core.tools import tool

if TYPE_CHECKING:
    from rag.memory_service import LongTermMemoryService

_memory: "LongTermMemoryService | None" = None
_memory_lock = Lock()


def _get_memory_service() -> "LongTermMemoryService":
    global _memory
    if _memory is None:
        with _memory_lock:
            if _memory is None:
                from rag.memory_service import LongTermMemoryService

                _memory = LongTermMemoryService()
    return _memory


@tool(description="将用户偏好或项目笔记写入长期向量记忆，支持指定user_id、scope、project标签")
def store_memory(note:str, user_id:str="global", scope:str="preference", project:str="") -> str:
    return _get_memory_service().add_memory(
        note=note,
        user_id=user_id,
        scope=scope,
        project=project,
    )


@tool(description="按query检索长期向量记忆，可按user_id、project过滤，返回相关记忆摘要")
def search_memory(query:str, user_id:str="global", project:str="") -> str:
    return _get_memory_service().search_memory(
        query=query,
        user_id=user_id,
        project=project,
    )
