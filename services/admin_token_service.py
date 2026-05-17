from __future__ import annotations

import os
import re
from pathlib import Path

from utils.path_tools import get_abs_path

ENV_PATH = Path(get_abs_path(".env"))
TOKEN_KEY = "APP_ADMIN_TOKEN"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._~!@#$%^&*+=:;,-]+$")


def _quote_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class AdminTokenService:
    def __init__(self, env_path: str | os.PathLike[str] | None = None) -> None:
        self.env_path = Path(env_path) if env_path is not None else ENV_PATH

    def update_token(self, new_token: str) -> dict[str, object]:
        token = new_token.strip()
        if len(token) < 12:
            return {
                "updated": False,
                "restart_required": False,
                "message": "管理 Token 至少需要 12 个字符。",
            }
        if not _TOKEN_RE.fullmatch(token):
            return {
                "updated": False,
                "restart_required": False,
                "message": "管理 Token 只能包含常见 ASCII 可见字符，不能包含空格或换行。",
            }

        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        lines = (
            self.env_path.read_text(encoding="utf-8-sig").splitlines()
            if self.env_path.exists()
            else []
        )
        assignment = f"{TOKEN_KEY}={_quote_env_value(token)}"
        next_lines: list[str] = []
        has_replaced = False

        for line in lines:
            stripped = line.strip()
            key_part = stripped.removeprefix("export ").split("=", 1)[0].strip()
            if "=" in stripped and key_part == TOKEN_KEY:
                if not has_replaced:
                    next_lines.append(assignment)
                    has_replaced = True
                continue
            next_lines.append(line)

        if not has_replaced:
            if next_lines and next_lines[-1].strip():
                next_lines.append("")
            next_lines.append(assignment)

        self.env_path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
        os.environ[TOKEN_KEY] = token
        return {
            "updated": True,
            "restart_required": False,
            "message": "管理 Token 已写入 .env，并已对当前后端进程生效。",
        }
