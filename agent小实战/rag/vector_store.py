from langchain_chroma import Chroma
from utils.config_handler import chroma_conf
from model.factory import embeddings_model
from langchain_text_splitters import RecursiveJsonSplitter
from utils.path_tools import get_abs_path
import os
from utils.file_handler import txt_loader ,pdf_loader

class VectorStpreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name = chroma_conf["collection_name"],
            embbedding_function = None,
            persist_directory = chroma_conf["persist_directory"]
        )
        self.spliter = RecursiveJsonSplitter(
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
                f.write(md5_for_check + "\n")
        
        def get_file_documents(read_path:str):
            if read_path.endswith(".txt"):
                return txt_loader(read_path)
            if read_path.endswith(".pdf"):
                return pdf_loader(read_path)
        
