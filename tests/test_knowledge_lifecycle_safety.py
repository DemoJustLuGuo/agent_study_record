import pytest

from rag.stores.snapshot_store import resolve_snapshot_path
from rag.vector_store import VectorStoreService
from services.knowledge_service import KnowledgeService


def test_vector_store_rollback_requires_exact_confirm_name() -> None:
    service = VectorStoreService.__new__(VectorStoreService)

    with pytest.raises(ValueError, match="confirm_name"):
        service.rollback_snapshot("snapshot_a", confirm_name="")

    with pytest.raises(ValueError, match="confirm_name"):
        service.rollback_snapshot("snapshot_a", confirm_name="snapshot_b")


def test_snapshot_restore_rejects_path_traversal(tmp_path) -> None:
    with pytest.raises(ValueError, match="快照名称"):
        resolve_snapshot_path(str(tmp_path), "../outside")


def test_knowledge_service_passes_rollback_confirmation() -> None:
    class FakeKnowledgeBase:
        def rollback_snapshot(self, snapshot_name, confirm_name=None):
            assert snapshot_name == "snapshot_a"
            assert confirm_name == "snapshot_a"
            return snapshot_name

    service = KnowledgeService(knowledge_base=FakeKnowledgeBase())

    result = service.rollback_snapshot("snapshot_a", "snapshot_a")

    assert result == {"snapshot": "snapshot_a", "result": "ok"}


def test_knowledge_service_reports_failed_rollback_confirmation() -> None:
    class FakeKnowledgeBase:
        def rollback_snapshot(self, snapshot_name, confirm_name=None):
            raise ValueError("回滚确认失败")

    service = KnowledgeService(knowledge_base=FakeKnowledgeBase())

    result = service.rollback_snapshot("snapshot_a", "wrong")

    assert result == {"error": "回滚确认失败"}
