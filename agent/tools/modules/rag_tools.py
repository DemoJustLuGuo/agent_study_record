from threading import Lock
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from pydantic import BaseModel, Field

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


class RAGSummarizeArgs(BaseModel):
    query: str = Field(
        description=(
            "用户的知识库检索问题。用于查询本地通信领域知识库，"
            "不用于实时网页事实核验。"
        )
    )


@tool(
    args_schema=RAGSummarizeArgs,
    description=(
        "从本地 Chroma 知识库检索通信领域参考资料并生成摘要回答。"
        "适用于术语解释、通信原理、项目资料和已入库文档问答。"
    ),
)
def rag_summarize(query: str) -> str:
    """检索本地知识库并返回面向用户的摘要回答。"""
    query = (query or "").strip()
    if not query:
        return format_tool_failure(
            tool_name="rag_summarize",
            reason="查询为空",
            solution="请提供明确的知识库检索问题后重试。",
        )

    try:
        return _get_rag_service().rag_summarize(query)
    except Exception as exc:
        return format_tool_failure(
            tool_name="rag_summarize",
            reason=f"检索异常: {str(exc)}",
            solution="请检查向量库状态与模型连接；必要时先在知识库管理页执行同步后重试。",
        )
