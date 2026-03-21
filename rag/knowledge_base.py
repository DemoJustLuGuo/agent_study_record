from rag.vector_store import VectorStoreService


class KnowledgeBaseService:
    def __init__(self):
        self.vector_store = VectorStoreService()

    def upload_by_str(self, data:str, filename:str, operator:str="admin") -> str:
        return self.vector_store.upload_text(
            data=data,
            filename=filename,
            operator=operator,
        )

    def sync_removed_sources(self) -> dict[str, object]:
        return self.vector_store.sync_removed_sources()

    def create_snapshot(self, tag:str="") -> str:
        return self.vector_store.create_snapshot(tag=tag)

    def rollback_snapshot(self, snapshot_name:str) -> str:
        return self.vector_store.rollback_snapshot(snapshot_name=snapshot_name)


