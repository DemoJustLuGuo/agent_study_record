from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import yaml

from utils.path_tools import get_abs_path

CONFIG_PATH = Path(get_abs_path("rag/config/chroma.yml"))

ALLOWED_CONFIG_FIELDS = {
    "retrieval": {
        "top_k": ("int", 1),
        "final_k": ("int", 1),
        "vector_k": ("int", 1),
        "keyword_k": ("int", 1),
        "candidate_k": ("int", 1),
        "hybrid_enabled": ("bool",),
        "keyword_enabled": ("bool",),
        "rerank": {
            "enabled": ("bool",),
            "target_chunk_length": ("int", 1),
            "weights": {
                "coverage": ("float", 0.0),
                "phrase": ("float", 0.0),
                "position": ("float", 0.0),
                "vector_rank": ("float", 0.0),
                "source_boost": ("float", 0.0),
                "length_penalty": ("float", 0.0),
            },
        },
    },
    "chunk_size": ("int", 1),
    "chunk_overlap": ("int", 0),
    "chunking": {
        "source_type": {
            "web_url": {
                "chunk_size": ("int", 1),
                "chunk_overlap": ("int", 0),
            }
        }
    },
}


def _path_label(path: tuple[str, ...]) -> str:
    return ".".join(path)


def _validate_scalar(
    value: Any, rule: tuple[Any, ...], path: tuple[str, ...]
) -> tuple[Any, str | None]:
    kind = rule[0]
    minimum = rule[1] if len(rule) > 1 else None
    label = _path_label(path)

    if kind == "bool":
        if isinstance(value, bool):
            return value, None
        return None, f"{label} 必须是布尔值。"

    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            return None, f"{label} 必须是整数。"
        if minimum is not None and value < minimum:
            return None, f"{label} 不能小于 {minimum}。"
        return value, None

    if kind == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, f"{label} 必须是数字。"
        number = float(value)
        if not math.isfinite(number):
            return None, f"{label} 必须是有限数字。"
        if minimum is not None and number < minimum:
            return None, f"{label} 不能小于 {minimum}。"
        return number, None

    return None, f"{label} 使用了不支持的配置类型。"


def _extract_allowed(
    source: dict[str, Any],
    template: dict[str, Any],
    prefix: tuple[str, ...] = (),
    *,
    warn_unknown: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    result: dict[str, Any] = {}
    warnings: list[str] = []

    for key in source:
        if warn_unknown and key not in template:
            warnings.append(f"忽略不允许修改的配置项：{_path_label(prefix + (key,))}。")

    for key, rule in template.items():
        if key not in source:
            continue
        path = prefix + (key,)
        value = source[key]
        if isinstance(rule, dict):
            if not isinstance(value, dict):
                warnings.append(f"{_path_label(path)} 必须是对象。")
                continue
            nested, nested_warnings = _extract_allowed(
                value,
                rule,
                path,
                warn_unknown=warn_unknown,
            )
            warnings.extend(nested_warnings)
            if nested:
                result[key] = nested
            continue

        scalar, warning = _validate_scalar(value, rule, path)
        if warning:
            warnings.append(warning)
            continue
        result[key] = scalar

    return result, warnings


def _merge_dicts(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_dicts(target[key], value)
            continue
        target[key] = value


class RagConfigService:
    def __init__(self, config_path: str | os.PathLike[str] | None = None) -> None:
        self.config_path = Path(config_path) if config_path is not None else CONFIG_PATH

    def get_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        allowed_config, _ = _extract_allowed(data, ALLOWED_CONFIG_FIELDS)
        return allowed_config

    def update_config(self, new_config: dict) -> dict:
        if not self.config_path.exists():
            return {
                "updated": False,
                "restart_required": False,
                "warnings": ["RAG 配置文件不存在。"],
            }
        if not isinstance(new_config, dict):
            return {
                "updated": False,
                "restart_required": False,
                "warnings": ["配置请求体必须是对象。"],
            }

        full_data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        allowed_updates, warnings = _extract_allowed(
            new_config,
            ALLOWED_CONFIG_FIELDS,
            warn_unknown=True,
        )
        if not allowed_updates:
            return {
                "updated": False,
                "restart_required": False,
                "warnings": warnings or ["没有可保存的配置变更。"],
            }

        _merge_dicts(full_data, allowed_updates)
        self.config_path.write_text(
            yaml.safe_dump(
                full_data,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        return {"updated": True, "restart_required": True, "warnings": warnings}
