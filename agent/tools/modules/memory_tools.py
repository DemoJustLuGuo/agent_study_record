from threading import Lock
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from pydantic import BaseModel, Field

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


class StoreMemoryArgs(BaseModel):
    note: str = Field(
        description=(
            "需要写入长期记忆的稳定事实、用户偏好或项目笔记。"
            "不要写入临时对话过程、敏感密钥或未经确认的推测。"
        )
    )
    user_id: str = Field(
        default="global", description="用户标识，单用户本地模式默认 global。"
    )
    scope: str = Field(
        default="preference",
        description="记忆范围标签，例如 preference、project、fact、constraint。",
    )
    project: str = Field(
        default="", description="可选项目标签，用于按项目隔离长期记忆。"
    )


class SearchMemoryArgs(BaseModel):
    query: str = Field(
        description="长期记忆检索问题，用于查找用户偏好、项目笔记或跨会话事实。"
    )
    user_id: str = Field(default="global", description="用户标识，默认 global。")
    project: str = Field(
        default="", description="可选项目过滤条件；为空时不按项目过滤。"
    )


@tool(
    args_schema=StoreMemoryArgs,
    description=(
        "将稳定的用户偏好、项目笔记或跨会话事实写入长期向量记忆。"
        "仅在用户明确要求记住，或内容明显属于长期项目上下文时使用。"
    ),
)
def store_memory(
    note: str, user_id: str = "global", scope: str = "preference", project: str = ""
) -> str:
    """写入长期向量记忆。"""
    note = (note or "").strip()
    if not note:
        return format_tool_failure(
            tool_name="store_memory",
            reason="记忆内容为空",
            solution="请提供需要长期保存的稳定事实、偏好或项目笔记后重试。",
        )

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


@tool(
    args_schema=SearchMemoryArgs,
    description=(
        "检索长期向量记忆，可按 user_id 和 project 过滤。"
        "适用于用户询问历史偏好、项目背景或跨会话上下文时。"
    ),
)
def search_memory(query: str, user_id: str = "global", project: str = "") -> str:
    """检索长期向量记忆并返回相关片段摘要。"""
    query = (query or "").strip()
    if not query:
        return format_tool_failure(
            tool_name="search_memory",
            reason="查询为空",
            solution="请提供明确的长期记忆检索问题后重试。",
        )

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
