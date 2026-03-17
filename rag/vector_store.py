import hashlib
import os
from datetime import datetime

from langchain_chroma import Chroma
from langchain_core.documents import Document
from utils.path_tools import get_abs_path
from utils.config_handler import chroma_conf
from model.factory import embeddings_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.file_handler import txt_loader,pdf_loader,listdir_with_allowed_type,get_file_md5_hex
from utils.log import logger

class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name = chroma_conf["collection_name"],
            embedding_function = embeddings_model,
            persist_directory = chroma_conf["persist_directory"],
        )
        self.spliter = RecursiveCharacterTextSplitter (
            chunk_size = chroma_conf["chunk_size"],
            chunk_overlap = chroma_conf["chunk_overlap"],
            separators = chroma_conf["separator"],
            length_function = len,
        )

    def _md5_store_path(self) -> str:
        return get_abs_path(chroma_conf["md5_hex_store"])

    def _check_md5_hex(self, md5_for_check:str) -> bool:
        md5_store_path = self._md5_store_path()
        if not os.path.exists(md5_store_path):
            open(md5_store_path, "w", encoding="utf-8").close()
            return False

        with open(md5_store_path, "r", encoding="utf-8") as f:
            for line in f.readlines():
                if line.strip() == md5_for_check:
                    return True

        return False

    def _save_md5_hex(self, md5_hex:str):
        with open(self._md5_store_path(), "a", encoding="utf-8") as f:
            f.write(md5_hex + "\n")

    def upload_text(self, data:str, filename:str, operator:str="admin") -> str:
        text = (data or "").strip()
        if not text:
            return "【失败】文本内容为空"

        md5_hex = hashlib.md5(text.encode("utf-8")).hexdigest()
        if self._check_md5_hex(md5_hex):
            logger.info("文本内容已存在于知识库中，跳过入库")
            return "【跳过】内容已经存在于知识库中"

        if len(text) > chroma_conf["chunk_size"]:
            knowledge_chunks:list[str] = self.spliter.split_text(text)
        else:
            knowledge_chunks = [text]

        if not knowledge_chunks:
            logger.warning("文本切分后为空，未执行入库")
            return "【失败】文本切分后为空"

        metadata = {
            "source": filename,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operator": operator,
        }

        self.vector_store.add_texts(
            knowledge_chunks,
            metadatas=[metadata for _ in knowledge_chunks],
        )
        self._save_md5_hex(md5_hex)
        logger.info(f"文本{filename}已成功上传到向量数据库")
        return "【成功】内容已成功添加到知识库中"
        
    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def load_documents(self):
        def get_file_documents(read_path:str):
            if read_path.endswith(".txt"):
                return txt_loader(read_path)
            if read_path.endswith(".pdf"):
                return pdf_loader(read_path)

            return []
        
        allowed_files_path:tuple[str, ...] = listdir_with_allowed_type(
        get_abs_path(chroma_conf["data_path"]),
        tuple(chroma_conf["allowed_knowledge_file_type"])
        )

        for path in allowed_files_path:
            md5_hex = get_file_md5_hex(path)
            if not md5_hex:
                logger.warning(f"文件{path}的MD5计算失败，跳过")
                continue

            if self._check_md5_hex(md5_hex):
                logger.info(f"文件{path}已处理过，跳过")
                continue
            try:
                documents : list[Document] = get_file_documents(path)
                if not documents:
                    logger.warning(f"文件{path}没有加载到任何文档，可能是格式不受支持")
                    continue
                split_document : list[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"文件{path}没有被分割成任何文档，可能是因为chunk_size设置过大")
                    continue


                self.vector_store.add_documents(split_document)
                self._save_md5_hex(md5_hex)
                logger.info(f"文件{path}已成功加载到向量数据库")
            except Exception as e:
                logger.error(f"加载文件{path}时发生错误: {str(e)}",exc_info=True)
                continue


if __name__ == "__main__":
    vector_store_service = VectorStoreService()
    vector_store_service.load_documents()

    retriever = vector_store_service.get_retriever()

    res = retriever.invoke("什么是RAG？")

    for r in res:
        print(r.page_content)
        print("-"*20)
