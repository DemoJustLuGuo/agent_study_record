from threading import Lock
from typing import TYPE_CHECKING

from langchain_core.tools import tool

from agent.tools.modules.shared import format_tool_failure

if TYPE_CHECKING:
    from rag.rag_service import RAGSummarizeService

_rag: "RAGSummarizeService | None" = None
_rag_lock = Lock()


def _get_rag_service() -> "RAGSummarizeService":
    global _rag
    with _rag_lock:
        if _rag is None:
            from rag.rag_service import RAGSummarizeService

            _rag = RAGSummarizeService()

    return _rag


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query:str) -> str:
    try:
        return _get_rag_service().rag_summarize(query)
    except Exception as exc:
        return format_tool_failure(
            tool_name="rag_summarize",
            reason=f"检索异常: {str(exc)}",
            solution="请检查向量库状态与模型连接；必要时先在知识库管理页执行同步后重试。",
        )
