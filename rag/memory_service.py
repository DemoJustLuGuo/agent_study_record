import hashlib
from datetime import datetime
from typing import List, Dict

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.vector_store import VectorStoreService
from utils.config_handler import chroma_conf
from utils.log import logger


class LongTermMemoryService:
    """Lightweight long-term memory built on existing Chroma store."""

    def __init__(self):
        # 记忆服务不需要在初始化时扫描 data 目录，避免重复开销。
        self.vector_service = VectorStoreService(enable_auto_sync=False)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separator"],
            length_function=len,
        )

    def _build_metadata(
        self, user_id: str, scope: str, project: str, note_md5: str
    ) -> Dict[str, str]:
        return {
            "source": f"memory/{user_id}/{note_md5}",
            "source_md5": note_md5,
            "source_type": "memory",
            "user_id": user_id or "global",
            "scope": scope or "general",
            "project": project or "",
            "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def add_memory(self, note: str, user_id: str = "global", scope: str = "preference", project: str = "") -> str:
        text = (note or "").strip()
        if not text:
            return "【失败】存储内容为空"

        note_md5 = hashlib.md5(text.encode("utf-8")).hexdigest()
        chunks: List[str] = self.splitter.split_text(text) if len(text) > chroma_conf["chunk_size"] else [text]
        metadata = self._build_metadata(user_id, scope, project, note_md5)

        # 覆盖写：先删除同一 source 的历史记录
        self.vector_service._delete_vectors_by_source(metadata["source"])
        self.vector_service.vector_store.add_texts(chunks, metadatas=[metadata] * len(chunks))
        logger.info(f"[memory] stored note for user={user_id}, scope={scope}, project={project}")
        return "【成功】记忆已写入长期存储"

    def search_memory(self, query: str, user_id: str = "global", project: str = "", k: int = None) -> str:
        q = (query or "").strip()
        if not q:
            return "【失败】查询内容为空"

        retriever = self.vector_service.vector_store.as_retriever(
            search_kwargs={
                "k": k or chroma_conf["k"],
                "filter": {
                    "source_type": "memory",
                    "user_id": user_id or "global",
                    **({"project": project} if project else {}),
                },
            }
        )

        docs = retriever.invoke(q)
        if not docs:
            return "【未命中】没有找到相关记忆"

        parts = []
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            scope = meta.get("scope", "general")
            proj = meta.get("project", "")
            ts = meta.get("indexed_at", "")
            prefix = f"{i}. [{scope}"
            if proj:
                prefix += f"/{proj}"
            prefix += f"] {ts}"
            parts.append(f"{prefix}\n{doc.page_content.strip()}")
        return "\n\n".join(parts)
