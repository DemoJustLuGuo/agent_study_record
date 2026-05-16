from __future__ import annotations

import os
import re


def looks_like_env_var(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", (value or "").strip()))


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
