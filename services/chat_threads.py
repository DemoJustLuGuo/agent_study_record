from __future__ import annotations

import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any

from utils.log import logger
from utils.path_tools import get_abs_path

THREAD_ID_PATTERN = re.compile(r"^thread_(\d+)$")
THREAD_DB_PATTERN = re.compile(r"^thread_(\d+)\.db$")
THREAD_TITLE_MAX_LEN = 50
MEMORY_DB_DIR = get_abs_path("memory_db")


class ChatThreadStore:
    def __init__(self) -> None:
        os.makedirs(MEMORY_DB_DIR, exist_ok=True)

    @staticmethod
    def _utc_now() -> str:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _norm_thread_id(thread_id: str) -> str:
        text = (thread_id or "").strip()
        if not THREAD_ID_PATTERN.match(text):
            raise ValueError(f"invalid thread_id: {thread_id}")
        return text

    def _db_path(self, thread_id: str) -> str:
        return os.path.join(MEMORY_DB_DIR, f"{self._norm_thread_id(thread_id)}.db")

    def _connect(self, thread_id: str) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path(thread_id), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        self._init_db(conn)
        return conn

    @staticmethod
    def _init_db(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS thread_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)
        conn.commit()

    @staticmethod
    def _set_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO thread_meta(key, value) VALUES (?, ?)",
            (key, str(value)),
        )

    @staticmethod
    def _get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
        row = conn.execute(
            "SELECT value FROM thread_meta WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return str(row["value"] or default)

    def _ensure_meta(self, conn: sqlite3.Connection, thread_id: str) -> None:
        idx = thread_id.removeprefix("thread_")
        title = self._get_meta(conn, "title", default=f"会话 {idx}")
        self._set_meta(conn, "thread_id", thread_id)
        self._set_meta(conn, "title", title[:THREAD_TITLE_MAX_LEN])
        if not self._get_meta(conn, "created_at", default=""):
            self._set_meta(conn, "created_at", self._utc_now())
        if not self._get_meta(conn, "updated_at", default=""):
            self._set_meta(conn, "updated_at", self._utc_now())
        if not self._get_meta(conn, "renamed", default=""):
            self._set_meta(conn, "renamed", "0")
        if not self._get_meta(conn, "auto_named", default=""):
            self._set_meta(conn, "auto_named", "0")
        conn.commit()

    def list_thread_ids(self) -> list[str]:
        ids: list[str] = []
        if not os.path.isdir(MEMORY_DB_DIR):
            return ids
        for name in os.listdir(MEMORY_DB_DIR):
            match = THREAD_DB_PATTERN.match(name)
            if not match:
                continue
            ids.append(f"thread_{int(match.group(1))}")
        ids.sort(key=lambda value: int(value.removeprefix("thread_")))
        return ids

    def list_threads(self) -> list[dict[str, Any]]:
        threads: list[dict[str, Any]] = []
        for thread_id in self.list_thread_ids():
            try:
                with closing(self._connect(thread_id)) as conn:
                    self._ensure_meta(conn, thread_id)
                    threads.append(
                        {
                            "thread_id": thread_id,
                            "title": self._get_meta(conn, "title", default=thread_id),
                            "renamed": self._get_meta(conn, "renamed", default="0")
                            == "1",
                            "auto_named": self._get_meta(
                                conn, "auto_named", default="0"
                            )
                            == "1",
                            "updated_at": self._get_meta(
                                conn, "updated_at", default=self._utc_now()
                            ),
                        }
                    )
            except Exception as error:
                logger.warning("读取会话失败: thread=%s reason=%s", thread_id, error)
        return threads

    def _next_thread_id(self) -> str:
        numbers = [
            int(thread_id.removeprefix("thread_"))
            for thread_id in self.list_thread_ids()
        ]
        next_idx = 1
        while next_idx in numbers:
            next_idx += 1
        return f"thread_{next_idx}"

    def create_thread(self) -> dict[str, Any]:
        thread_id = self._next_thread_id()
        with closing(self._connect(thread_id)) as conn:
            self._ensure_meta(conn, thread_id)
            conn.commit()
            title = self._get_meta(conn, "title", default=thread_id)
        logger.info("[chat] create thread=%s", thread_id)
        return {
            "thread_id": thread_id,
            "title": title,
            "renamed": False,
            "auto_named": False,
        }

    def rename_thread(self, thread_id: str, title: str, manual: bool = True) -> str:
        thread_id = self._norm_thread_id(thread_id)
        normalized = (title or "").strip()
        if not normalized:
            raise ValueError("会话名称不能为空")
        if len(normalized) > THREAD_TITLE_MAX_LEN:
            raise ValueError(f"会话名称长度不能超过 {THREAD_TITLE_MAX_LEN} 字")
        with closing(self._connect(thread_id)) as conn:
            self._ensure_meta(conn, thread_id)
            self._set_meta(conn, "title", normalized)
            self._set_meta(conn, "updated_at", self._utc_now())
            if manual:
                self._set_meta(conn, "renamed", "1")
            else:
                self._set_meta(conn, "auto_named", "1")
            conn.commit()
        logger.info(
            "[chat] rename thread=%s manual=%s title=%s", thread_id, manual, normalized
        )
        return normalized

    def delete_thread(self, thread_id: str) -> None:
        thread_id = self._norm_thread_id(thread_id)
        db_path = self._db_path(thread_id)
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info("[chat] delete thread=%s", thread_id)

    def append_message(self, thread_id: str, role: str, content: str) -> None:
        thread_id = self._norm_thread_id(thread_id)
        text = (content or "").strip()
        if not text:
            return
        normalized_role = "assistant" if str(role).strip() == "assistant" else "user"
        with closing(self._connect(thread_id)) as conn:
            self._ensure_meta(conn, thread_id)
            conn.execute(
                "INSERT INTO chat_messages(role, content, created_at) VALUES (?, ?, ?)",
                (normalized_role, text, self._utc_now()),
            )
            self._set_meta(conn, "updated_at", self._utc_now())
            conn.commit()

    def load_messages(self, thread_id: str) -> list[dict[str, str]]:
        thread_id = self._norm_thread_id(thread_id)
        with closing(self._connect(thread_id)) as conn:
            self._ensure_meta(conn, thread_id)
            rows = conn.execute(
                "SELECT role, content FROM chat_messages ORDER BY id ASC"
            ).fetchall()
        messages: list[dict[str, str]] = []
        for row in rows:
            role = str(row["role"] or "").strip()
            if role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": str(row["content"] or "")})
        return messages

    def get_title(self, thread_id: str) -> str:
        thread_id = self._norm_thread_id(thread_id)
        with closing(self._connect(thread_id)) as conn:
            self._ensure_meta(conn, thread_id)
            return self._get_meta(conn, "title", default=thread_id)

    def get_flags(self, thread_id: str) -> dict[str, bool]:
        thread_id = self._norm_thread_id(thread_id)
        with closing(self._connect(thread_id)) as conn:
            self._ensure_meta(conn, thread_id)
            return {
                "renamed": self._get_meta(conn, "renamed", default="0") == "1",
                "auto_named": self._get_meta(conn, "auto_named", default="0") == "1",
            }
