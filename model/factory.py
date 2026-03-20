from abc import ABC, abstractmethod
import os
import re
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from utils.config_handler import agent_conf


def _configured_openai_api_key_value() -> str:
    return str(
        agent_conf.get("OPENAI_API_KEY", agent_conf.get("SILICONFLOW_API_KEY", ""))
    ).strip()


def _looks_like_env_var(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", value))


def _resolve_config_secret(config_value: str) -> Optional[str]:
    if not config_value:
        return None

    env_value = (os.environ.get(config_value) or "").strip()
    if env_value:
        return env_value

    if _looks_like_env_var(config_value):
        return None

    # 兼容直接在配置中填写密钥值的场景（不推荐）。
    return config_value


def _validate_openai_api_key_startup() -> None:
    config_value = _configured_openai_api_key_value()
    if not config_value:
        return

    if _resolve_config_secret(config_value):
        return

    raise RuntimeError(
        "启动失败：config/agent.yml 中已声明 OPENAI_API_KEY="
        f"{config_value}，但当前环境变量未设置或为空。\n"
        f"请先在系统环境变量中配置 {config_value} 后再启动。"
    )


def _resolve_openai_api_key() -> Optional[str]:
    return _resolve_config_secret(_configured_openai_api_key_value())


def _resolve_openai_base_url() -> Optional[str]:
    base_url = str(agent_conf.get("openai_base_url", agent_conf.get("OPENAI_BASE_URL", ""))).strip()
    return base_url or None


def _build_openai_client_kwargs() -> dict:
    kwargs = {}
    api_key = _resolve_openai_api_key()
    base_url = _resolve_openai_base_url()
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    return kwargs


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass



class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        kwargs = _build_openai_client_kwargs()
        try:
            kwargs["temperature"] = float(agent_conf.get("chat_temperature", 0))
        except (TypeError, ValueError):
            kwargs["temperature"] = 0

        return ChatOpenAI(
            model=agent_conf["chat_model_name"],
            **kwargs,
        )


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return OpenAIEmbeddings(
            model=agent_conf["embedding_model_name"],
            **_build_openai_client_kwargs(),
        )


_validate_openai_api_key_startup()

chat_model = ChatModelFactory().generator()
embeddings_model = EmbeddingsFactory().generator()
