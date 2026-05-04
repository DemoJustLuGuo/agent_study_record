from __future__ import annotations

from typing import Any

from rag.metrics import record_rag_metric
from rag.rag_service import RAGSummarizeService
from utils.log import logger


class RagQueryService:
    def __init__(self, rag_service: RAGSummarizeService | None = None) -> None:
        self.rag_service = rag_service or RAGSummarizeService()

    def answer_with_references(self, query: str) -> dict[str, Any]:
        text = (query or "").strip()
        if not text:
            return {"error": "请输入问题。"}

        try:
            logger.info("[rag] query start len=%s", len(text))
            result = self.rag_service.answer_with_references(text)
        except Exception:
            logger.exception("[rag] query failed")
            record_rag_metric(
                {
                    "ok": False,
                    "strategy": "error",
                    "reference_count": 0,
                    "candidate_count": 0,
                    "retrieval_ms": 0,
                    "rerank_ms": 0,
                    "llm_ms": 0,
                    "total_ms": 0,
                }
            )
            return {"error": "⚠️ 系统错误：RAG 查询失败，请稍后重试。"}

        references = result.get("references", [])
        metrics = result.get("metrics", {})
        record_rag_metric(
            {
                "ok": True,
                "strategy": metrics.get("strategy", "unknown"),
                "reference_count": metrics.get("reference_count", len(references)),
                "candidate_count": metrics.get("candidate_count", 0),
                "retrieval_ms": metrics.get("retrieval_ms", 0),
                "rerank_ms": metrics.get("rerank_ms", 0),
                "llm_ms": metrics.get("llm_ms", 0),
                "total_ms": metrics.get("total_ms", 0),
            }
        )
        logger.info("[rag] query done refs=%s", len(references))
        return result
