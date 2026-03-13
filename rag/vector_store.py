import os


from langchain_core.documents import Document
from utils.path_tools import get_abs_path
from utils.config_handler import chroma_conf
from model.factory import embeddings_model
from langchain_text_splitters import RecursiveJsonSplitter
from utils.file_handler import txt_loader,pdf_loader,listdir_with_allowed_type,get_file_md5_hex
from utils.logger_handler import logger

class VectorStpreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name = chroma_conf["collection_name"],
            embbedding_function = None,
            persist_directory = chroma_conf["persist_directory"]
        )
        self.spliter = RecursivecharacterTextSplitter(
            chunk_size = chroma_conf["chunk_size"],
            chunk_overlap = chroma_conf["chunk_overlap"],
            separators = chroma_conf["separators"],
            length_function = len,
        )
        
    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def load_documents(self,documents):
        def check_md5_hex(md5_for_check:str):
            if not os.path.exists(get_abs_path(chroma_conf("md5_hex_store"))):
                open(get_abs_path(chroma_conf["md5_hex_store"]), "w").close()
                return False

            with open(get_abs_path(chroma_conf["md5_hex_store"]), "r") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == md5_for_check:
                        return True
                return False

        def save_md5_hex(md5_hex:str):
            with open(get_abs_path(chroma_conf["md5_hex_store"]), "a",encoding="UTF-8") as f:
                f.write( md5_for_check + "\n")
        
        def get_file_documents(read_path:str):
            if read_path.endswith(".txt"):
                return txt_loader(read_path)
            if read_path.endswith(".pdf"):
                return pdf_loader(read_path)

            return []
        
        allowed_files_path = listdir_with_allowed_type(chroma_conf["data_path"],
        tuple(chroma_conf["allowed_knowledge_file_type"])
        )

        for path in allowed_files_path:
            md5_hex = get_file_md5_hex(path)
            if check_md5_hex(md5_hex):
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
                save_md5_hex(md5_hex)
                logger.info(f"文件{path}已成功加载到向量数据库")
            except Exception as e:
                logger.error(f"加载文件{path}时发生错误: {str(e)}",exec_info=True)
                continue


if __name__ == "__main__":
    vector_store_service = VectorStpreService()
    vector_store_service.load_documents()

    retriever = vector_store_service.get_retriever()

    res = retriever.invoke("什么是RAG？")

    for r in res:
        print(r.page_content)
        print("-"*20)
