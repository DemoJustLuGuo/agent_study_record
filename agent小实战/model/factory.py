from abc import ABC, abstractmethod
from typing import Optional
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_siliconflow import ChatSiliconFlow
from langchain.embeddings import Embbeddings
from langchain_siliconflow import BaseChatModel
from utils.config_handler import rag_conf

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embbeddings | BaseChatModel]:
        pass



class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embbeddings | BaseChatModel]:
        return ChatSiliconFlow(model=rag_conf["chat_model_name"])


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embbeddings | BaseChatModel]:
        return DashScopeEmbeddings(model=reg_conf["embeddings_model_name"])

chat_model = ChatModelFactory().generator()
embeddings_model = EmbeddingsFactory().generator()
