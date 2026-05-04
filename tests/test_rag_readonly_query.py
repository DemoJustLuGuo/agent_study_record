from langchain_core.documents import Document

from rag.rag_service import RAGSummarizeService
from rag.vector_store import VectorStoreService


class _FakeChain:
    def invoke(self, payload):
        assert payload["input"] == "OFDM 是什么"
        return "OFDM 是一种多载波调制技术。"


class _FakeReadOnlyVectorStore:
    auto_sync_before_retrieval = True

    def auto_sync_data_dir(self, trigger: str = "runtime"):
        raise AssertionError(f"query path must not sync data dir: {trigger}")

    def hybrid_retrieve(self, query: str):
        assert query == "OFDM 是什么"
        return [Document(page_content="OFDM 使用多个正交子载波。", metadata={})], {
            "strategy": "test",
            "candidate_count": 1,
        }


def test_rag_answer_query_does_not_auto_sync_before_retrieval() -> None:
    service = RAGSummarizeService.__new__(RAGSummarizeService)
    service.vector_store = _FakeReadOnlyVectorStore()
    service.chain = _FakeChain()

    result = service.answer_with_references("OFDM 是什么")

    assert result["answer"] == "OFDM 是一种多载波调制技术。"
    assert result["metrics"]["reference_count"] == 1


def test_get_retriever_does_not_auto_sync() -> None:
    class FakeVectorStore:
        def as_retriever(self, search_kwargs):
            return {"search_kwargs": search_kwargs}

    service = VectorStoreService.__new__(VectorStoreService)
    service.enable_auto_sync = True
    service.auto_sync_before_retrieval = True
    service.vector_store = FakeVectorStore()

    def fail_sync(trigger: str = "runtime"):
        raise AssertionError(f"get_retriever must not sync data dir: {trigger}")

    service.auto_sync_data_dir = fail_sync

    retriever = service.get_retriever()

    assert retriever["search_kwargs"]["k"] >= 1
