from utils.config_handler import agent_conf, chroma_conf
from utils.path_tools import get_abs_path


md5_path = get_abs_path(chroma_conf["md5_hex_store"])
collection_name = chroma_conf["collection_name"]
embedding_function = agent_conf["embedding_model_name"]
persist_directory = get_abs_path(chroma_conf["persist_directory"])
chunk_size = chroma_conf["chunk_size"]
chunk_overlap = chroma_conf["chunk_overlap"]
separators = chroma_conf["separator"]
max_split_char_number = chroma_conf["chunk_size"]
