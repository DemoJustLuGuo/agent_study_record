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


if __name__ == "__main__":
    service = KnowledgeBaseService()
    print(service.upload_by_str("这是一个测试字符串", "test.txt"))