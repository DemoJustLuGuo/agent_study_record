import math
import re
import time
from typing import Any

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from model.factory import chat_model
from rag.vector_store import VectorStoreService
from utils.config_handler import chroma_conf
from utils.log import logger
from utils.prompt_loader import load_rag_prompt


class RAGSummarizeService:
    def __init__(self):
        self.vector_store = VectorStoreService(enable_auto_sync=True)
        self.prompt_text = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        return self.prompt_template | self.model | StrOutputParser()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", (text or "").lower())

    @staticmethod
    def _source_weight(source_type: str, weight_conf: dict[str, float]) -> float:
        if source_type in weight_conf:
            return float(weight_conf[source_type])
        return float(weight_conf.get("default", 0.0))

    def _heuristic_rerank(
        self,
        query: str,
        candidates: list[Document],
        retrieval_conf: dict[str, Any],
    ) -> tuple[list[Document], list[dict[str, Any]]]:
        rerank_conf = retrieval_conf.get("rerank", {})
        final_k = int(
            rerank_conf.get(
                "final_k", retrieval_conf.get("final_k", chroma_conf.get("k", 3))
            )
        )
        weights = rerank_conf.get("weights", {})
        source_weight_conf = rerank_conf.get("source_type_weights", {})
        query_text = (query or "").strip().lower()
        query_tokens = self._tokenize(query)
        query_token_set = set(query_tokens)

        if not candidates:
            return [], []
        if not query_token_set:
            return candidates[:final_k], []

        scored: list[tuple[float, Document, dict[str, Any]]] = []
        for rank, doc in enumerate(candidates, start=1):
            content = (doc.page_content or "").strip()
            content_lower = content.lower()
            doc_tokens = self._tokenize(content)
            doc_token_set = set(doc_tokens)

            coverage = len(query_token_set & doc_token_set) / max(
                1, len(query_token_set)
            )
            phrase = 1.0 if query_text and query_text in content_lower else 0.0
            first_hit = min(
                [
                    content_lower.find(token)
                    for token in query_token_set
                    if token and content_lower.find(token) >= 0
                ]
                or [-1]
            )
            position = 0.0 if first_hit < 0 else 1.0 / (1.0 + first_hit / 120.0)
            target_len = int(rerank_conf.get("target_chunk_length", 360))
            len_penalty = abs(len(content) - target_len) / max(target_len, 1)
            source_type = str((doc.metadata or {}).get("source_type", "unknown"))
            source_boost = self._source_weight(source_type, source_weight_conf)
            vector_rank_score = 1.0 / (1.0 + math.log1p(rank))

            score = (
                float(weights.get("coverage", 1.8)) * coverage
                + float(weights.get("phrase", 1.0)) * phrase
                + float(weights.get("position", 0.6)) * position
                + float(weights.get("vector_rank", 0.4)) * vector_rank_score
                + float(weights.get("source_boost", 0.4)) * source_boost
                - float(weights.get("length_penalty", 0.35)) * len_penalty
            )
            details = {
                "source": str((doc.metadata or {}).get("source", "")),
                "source_type": source_type,
                "coverage": round(coverage, 4),
                "phrase": round(phrase, 4),
                "position": round(position, 4),
                "vector_rank_score": round(vector_rank_score, 4),
                "source_boost": round(source_boost, 4),
                "length_penalty": round(len_penalty, 4),
                "score": round(score, 6),
            }
            scored.append((score, doc, details))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_docs = [item[1] for item in scored[:final_k]]
        top_details = [item[2] for item in scored[:final_k]]
        return top_docs, top_details

    @staticmethod
    def _build_context(context_docs: list[Document]) -> str:
        context_blocks = []
        for index, doc in enumerate(context_docs, start=1):
            context_blocks.append(
                f"【参考资料{index}】{doc.page_content}\n" f"【元数据】{doc.metadata}"
            )
        return "\n\n".join(context_blocks)

    def answer_with_references(self, query: str) -> dict[str, Any]:
        if self.vector_store.auto_sync_before_retrieval:
            self.vector_store.auto_sync_data_dir(trigger="rag_query")

        retrieval_conf = chroma_conf.get("retrieval", {})
        rerank_conf = retrieval_conf.get("rerank", {})
        rerank_enabled = bool(rerank_conf.get("enabled", True))

        retrieve_start = time.perf_counter()
        candidates, retrieval_debug = self.vector_store.hybrid_retrieve(query)
        retrieve_elapsed_ms = int((time.perf_counter() - retrieve_start) * 1000)

        rerank_elapsed_ms = 0
        rerank_details: list[dict[str, Any]] = []
        if rerank_enabled:
            rerank_start = time.perf_counter()
            context_docs, rerank_details = self._heuristic_rerank(
                query=query,
                candidates=candidates,
                retrieval_conf=retrieval_conf,
            )
            rerank_elapsed_ms = int((time.perf_counter() - rerank_start) * 1000)
        else:
            final_k = int(retrieval_conf.get("final_k", chroma_conf.get("k", 3)))
            context_docs = candidates[:final_k]

        context = self._build_context(context_docs)
        llm_start = time.perf_counter()
        answer = self.chain.invoke({"input": query, "context": context})
        llm_elapsed_ms = int((time.perf_counter() - llm_start) * 1000)

        references = [
            {"content": doc.page_content, "metadata": doc.metadata}
            for doc in context_docs
        ]
        total_elapsed_ms = retrieve_elapsed_ms + rerank_elapsed_ms + llm_elapsed_ms
        logger.info(
            "[rag] 检索完成 strategy=%s candidates=%s final=%s retrieve_ms=%s rerank_ms=%s llm_ms=%s",
            retrieval_debug.get("strategy", "unknown"),
            retrieval_debug.get("candidate_count", len(candidates)),
            len(references),
            retrieve_elapsed_ms,
            rerank_elapsed_ms,
            llm_elapsed_ms,
        )
        return {
            "query": query,
            "answer": answer,
            "references": references,
            "retrieval_debug": retrieval_debug,
            "rerank_debug": rerank_details,
            "metrics": {
                "retrieval_ms": retrieve_elapsed_ms,
                "rerank_ms": rerank_elapsed_ms,
                "llm_ms": llm_elapsed_ms,
                "total_ms": total_elapsed_ms,
                "candidate_count": int(
                    retrieval_debug.get("candidate_count", len(candidates))
                ),
                "reference_count": len(references),
                "strategy": retrieval_debug.get("strategy", "unknown"),
            },
        }

    def rag_summarize(self, query: str) -> str:
        return self.answer_with_references(query)["answer"]
