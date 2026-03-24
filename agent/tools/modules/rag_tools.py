from threading import Lock
from typing import TYPE_CHECKING

from langchain_core.tools import tool

if TYPE_CHECKING:
    from rag.rag_service import RAGSummarizeService

_rag: "RAGSummarizeService | None" = None
_rag_lock = Lock()


def _get_rag_service() -> "RAGSummarizeService":
    global _rag
    if _rag is None:
        with _rag_lock:
            if _rag is None:
                from rag.rag_service import RAGSummarizeService

                _rag = RAGSummarizeService()
    return _rag


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query:str) -> str:
    return _get_rag_service().rag_summarize(query)
