from threading import Lock
from typing import TYPE_CHECKING

from langchain_core.tools import tool

from agent.tools.modules.shared import format_tool_failure

if TYPE_CHECKING:
    from rag.memory_service import LongTermMemoryService

_memory: "LongTermMemoryService | None" = None
_memory_lock = Lock()


def _get_memory_service() -> "LongTermMemoryService":
    global _memory
    with _memory_lock:
        if _memory is None:
            from rag.memory_service import LongTermMemoryService

            _memory = LongTermMemoryService()

    return _memory


@tool(description="将用户偏好或项目笔记写入长期向量记忆，支持指定user_id、scope、project标签")
def store_memory(note:str, user_id:str="global", scope:str="preference", project:str="") -> str:
    try:
        return _get_memory_service().add_memory(
            note=note,
            user_id=user_id,
            scope=scope,
            project=project,
        )
    except Exception as exc:
        return format_tool_failure(
            tool_name="store_memory",
            reason=f"写入异常: {str(exc)}",
            solution="请检查记忆库配置与向量库连接，确认输入内容合法后重试。",
        )


@tool(description="按query检索长期向量记忆，可按user_id、project过滤，返回相关记忆摘要")
def search_memory(query:str, user_id:str="global", project:str="") -> str:
    try:
        return _get_memory_service().search_memory(
            query=query,
            user_id=user_id,
            project=project,
        )
    except Exception as exc:
        return format_tool_failure(
            tool_name="search_memory",
            reason=f"检索异常: {str(exc)}",
            solution="请检查记忆库索引状态与过滤参数后重试。",
        )
