from typing import Any

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from model.factory import chat_model
from rag.vector_store import VectorStoreService
from utils.log import logger
from utils.prompt_loader import load_rag_prompt


class RAGSummarizeService:
    def __init__(self):
        self.vector_store = VectorStoreService(enable_auto_sync=True)
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()


    def _init_chain(self):
        return self.prompt_template | self.model | StrOutputParser()

    def retriever_docs(self, query:str) -> list[Document]:
        return self.retriever.invoke(query)

    @staticmethod
    def _build_context(context_docs:list[Document]) -> str:
        context_blocks = []
        for index, doc in enumerate(context_docs, start=1):
            context_blocks.append(
                f"【参考资料{index}】{doc.page_content}\n"
                f"【元数据】{doc.metadata}"
            )
        return "\n\n".join(context_blocks)

    def answer_with_references(self, query:str) -> dict[str, Any]:
        if self.vector_store.auto_sync_before_retrieval:
            self.vector_store.auto_sync_data_dir(trigger="rag_query")

        context_docs = self.retriever_docs(query)
        context = self._build_context(context_docs)

        answer = self.chain.invoke(
            {
                "input": query,
                "context": context,
            }
        )

        references = [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
            }
            for doc in context_docs
        ]

        logger.info(f"在线RAG检索完成，命中片段数量: {len(references)}")
        return {
            "query": query,
            "answer": answer,
            "references": references,
        }

    def rag_summarize(self, query:str) -> str:
        return self.answer_with_references(query)["answer"]




