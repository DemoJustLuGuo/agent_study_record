from __future__ import annotations

import os
import re
from typing import Any

import yaml

from utils.path_tools import get_abs_path

AGENT_CONFIG_PATH = get_abs_path("model/config/agent.yml")


def looks_like_env_var(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", (value or "").strip()))


def read_agent_config() -> dict[str, Any]:
    try:
        with open(AGENT_CONFIG_PATH, "r", encoding="utf-8") as file_obj:
            data = yaml.safe_load(file_obj) or {}
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}


def write_agent_config(config_data: dict[str, Any]) -> None:
    config_dir = os.path.dirname(AGENT_CONFIG_PATH)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    with open(AGENT_CONFIG_PATH, "w", encoding="utf-8") as file_obj:
        yaml.safe_dump(config_data, file_obj, allow_unicode=True, sort_keys=False)


def mask_secret(secret: str) -> str:
    value = (secret or "").strip()
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def resolve_secret(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    env_value = (os.environ.get(text) or "").strip()
    if env_value:
        return env_value
    if looks_like_env_var(text):
        return ""
    return text


def load_connection_defaults() -> tuple[str, str, str]:
    config_data = read_agent_config()
    base_url = str(config_data.get("openai_base_url", "")).strip()
    key_value = str(config_data.get("OPENAI_API_KEY", "")).strip()

    if looks_like_env_var(key_value):
        status = (
            "当前 `OPENAI_API_KEY` 配置为环境变量名，"
            "请在运行环境中设置真实密钥；不会把真实密钥写入配置文件。"
        )
        return base_url, "", status

    if key_value:
        status = (
            f"已读取现有配置：API 地址 `{base_url}`，"
            f"API Key `{mask_secret(key_value)}`。建议迁移为环境变量名。"
        )
    else:
        status = "尚未配置 OpenAI API 地址与密钥。"
    return base_url, key_value, status


def save_connection_settings(openai_base_url: str, openai_api_key: str) -> str:
    base_url = (openai_base_url or "").strip()
    api_key = (openai_api_key or "").strip()

    if not base_url:
        return "⚠️ API 地址为空，未保存。"
    if not api_key:
        return "⚠️ API 密钥为空，未保存。"

    config_data = read_agent_config()
    config_data["openai_base_url"] = base_url
    if looks_like_env_var(api_key):
        config_data["OPENAI_API_KEY"] = api_key
        write_agent_config(config_data)
        return (
            f"✅ 已保存到 `model/config/agent.yml`：API 地址 `{base_url}`，"
            f"API Key 环境变量名 `{api_key}`。"
        )

    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["SILICONFLOW_API_KEY"] = api_key
    config_data["OPENAI_API_KEY"] = "SILICONFLOW_API_KEY"
    write_agent_config(config_data)
    return (
        "✅ 已写入当前进程环境变量，未把真实 API Key 写入配置文件："
        f"API 地址 `{base_url}`，API Key `{mask_secret(api_key)}`。"
    )
