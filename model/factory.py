from abc import ABC, abstractmethod
from typing import Optional
from langchain_siliconflow.embeddings import Embeddings
from langchain_siliconflow import ChatSiliconFlow
from langchain_core.embeddings import Embeddings
from langchain_siliconflow.chat_models import BaseChatOpenAI
from utils.config_handler import rag_conf

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatOpenAI]:
        pass



class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatOpenAI]:
        return ChatSiliconFlow(model=rag_conf["chat_model_name"])


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatOpenAI]:
        return Embeddings(model=rag_conf["embedding_model_name"])

chat_model = ChatModelFactory().generator()
embeddings_model = EmbeddingsFactory().generator()
