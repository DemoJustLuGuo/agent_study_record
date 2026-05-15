from __future__ import annotations

import os
import re
from pathlib import Path

from utils.path_tools import get_abs_path

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    for index, char in enumerate(value):
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
            continue
        if char == "#" and quote is None:
            return value[:index].rstrip()
    return value.strip()


def _unquote(value: str) -> str:
    text = _strip_inline_comment(value)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def load_project_dotenv(path: str | os.PathLike[str] | None = None) -> None:
    """Load project .env values without overriding explicit process env."""

    env_path = Path(path or get_abs_path(".env"))
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not _ENV_KEY_RE.fullmatch(key) or key in os.environ:
            continue
        os.environ[key] = _unquote(raw_value)
