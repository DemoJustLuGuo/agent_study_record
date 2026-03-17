from abc import ABC, abstractmethod
import os
from typing import Optional
from langchain_siliconflow.embeddings import SiliconFlowEmbeddings
from langchain_siliconflow import ChatSiliconFlow
from langchain_core.embeddings import Embeddings
from langchain_siliconflow.chat_models import BaseChatOpenAI
from utils.config_handler import rag_conf


def _configured_api_key_var_name() -> str:
    return str(rag_conf.get("SILICONFLOW_API_KEY", "")).strip()


def _validate_siliconflow_api_key_startup() -> None:
    config_value = _configured_api_key_var_name()
    if not config_value:
        return

    # 兼容直接在配置中填写密钥值的场景。
    if config_value.startswith("sk-"):
        return

    env_value = (os.environ.get(config_value) or "").strip()
    if env_value:
        return

    raise RuntimeError(
        "启动失败：config/rag.yml 中已声明 SILICONFLOW_API_KEY="
        f"{config_value}，但当前环境变量未设置或为空。\n"
        f"请先在系统环境变量中配置 {config_value} 后再启动。"
    )


def _resolve_siliconflow_api_key() -> Optional[str]:
    config_value = _configured_api_key_var_name()
    if not config_value:
        return None

    # 兼容直接在配置中填写密钥值的场景（不推荐）。
    if config_value.startswith("sk-"):
        return config_value

    env_value = (os.environ.get(config_value) or "").strip()
    if env_value:
        return env_value

    return None

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatOpenAI]:
        pass



class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatOpenAI]:
        return ChatSiliconFlow(
            model=rag_conf["chat_model_name"],
            api_key=_resolve_siliconflow_api_key(),
        )


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatOpenAI]:
        return SiliconFlowEmbeddings(
            model=rag_conf["embedding_model_name"],
            api_key=_resolve_siliconflow_api_key(),
        )


_validate_siliconflow_api_key_startup()

chat_model = ChatModelFactory().generator()
embeddings_model = EmbeddingsFactory().generator()
