from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Iterator

from langchain_openai import ChatOpenAI

from agent.events import AgentEvent
from app.chat_threads import ChatThreadStore, THREAD_TITLE_MAX_LEN
from services.settings_service import resolve_secret
from utils.config_handler import memory_conf
from utils.log import logger
from utils.path_tools import get_abs_path

CHAT_EVENT_TYPES = {"status", "token", "tool", "references", "done", "error"}


@dataclass(frozen=True)
class ChatEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in CHAT_EVENT_TYPES:
            raise ValueError(f"unsupported chat event type: {self.type}")


def _build_title_model() -> ChatOpenAI:
    conf = memory_conf.get("summarizer_model", {})
    model_name = str(conf.get("model_name", "")).strip() or "Pro/MiniMaxAI/MiniMax-M2.5"
    temperature = float(conf.get("temperature", 0.2))
    kwargs: dict[str, Any] = {"model": model_name, "temperature": temperature}
    base_url = str(conf.get("base_url", "")).strip()
    api_key = resolve_secret(str(conf.get("api_key", "")).strip())
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    return ChatOpenAI(**kwargs)


class ChatService:
    def __init__(
        self,
        store: ChatThreadStore | None = None,
        agent_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        self.store = store or ChatThreadStore()
        self._agent_factory = agent_factory
        self._thread_agents: dict[str, Any] = {}
        self._thread_agents_lock = Lock()
        self._stream_locks: dict[str, Lock] = {}
        self._stream_locks_lock = Lock()

    def _ensure_thread_exists(self, thread_id: str | None = None) -> str:
        all_ids = set(self.store.list_thread_ids())
        text = (thread_id or "").strip()
        if text and text in all_ids:
            return text
        created = self.store.create_thread()
        return str(created["thread_id"])

    @staticmethod
    def _thread_choices(threads: list[dict[str, Any]]) -> list[tuple[str, str]]:
        return [
            (f"{item.get('title', item.get('thread_id', '会话'))}", item["thread_id"])
            for item in threads
        ]

    def _stream_lock_for(self, thread_id: str) -> Lock:
        with self._stream_locks_lock:
            lock = self._stream_locks.get(thread_id)
            if lock is None:
                lock = Lock()
                self._stream_locks[thread_id] = lock
            return lock

    def get_agent(self, thread_id: str) -> Any:
        with self._thread_agents_lock:
            cached = self._thread_agents.get(thread_id)
            if cached is not None:
                return cached
            if self._agent_factory is not None:
                runtime_agent = self._agent_factory(
                    thread_id, get_abs_path(f"memory_db/{thread_id}.db")
                )
            else:
                from agent.react_agent import ReactAgent

                runtime_agent = ReactAgent(
                    thread_id=thread_id,
                    db_path=get_abs_path(f"memory_db/{thread_id}.db"),
                )
            self._thread_agents[thread_id] = runtime_agent
            return runtime_agent

    def close_agent(self, thread_id: str) -> None:
        with self._thread_agents_lock:
            runtime_agent = self._thread_agents.pop(thread_id, None)
        if runtime_agent is None:
            return
        try:
            runtime_agent.close()
        except Exception:
            logger.debug("[chat] close agent failed thread=%s", thread_id)

    def chat_status(self, thread_id: str, extra: str = "") -> str:
        title = self.store.get_title(thread_id)
        base = f"当前会话：`{title}`（{thread_id}）"
        if extra:
            return f"{base} · {extra}"
        return base

    def get_thread_list(self) -> list[dict[str, Any]]:
        return self.store.list_threads()

    def get_initial_state_data(self) -> dict[str, Any]:
        threads = self.store.list_threads()
        if not threads:
            created = self.store.create_thread()
            thread_id = str(created["thread_id"])
        else:
            thread_id = str(threads[0]["thread_id"])
        threads = self.store.list_threads()
        return {
            "threads": threads,
            "choices": self._thread_choices(threads),
            "history": self.store.load_messages(thread_id),
            "thread_id": thread_id,
            "status": self.chat_status(thread_id),
        }

    def create_thread(self, current_thread_id: str = "") -> dict[str, Any]:
        created = self.store.create_thread()
        thread_id = str(created["thread_id"])
        logger.debug(
            "[chat][service] thread_create current=%s created=%s",
            (current_thread_id or "").strip(),
            thread_id,
        )
        threads = self.store.list_threads()
        return {
            "threads": threads,
            "choices": self._thread_choices(threads),
            "history": [],
            "thread_id": thread_id,
            "status": self.chat_status(thread_id, "已创建新会话"),
        }

    def switch_thread(self, thread_id: str) -> dict[str, Any]:
        selected = self._ensure_thread_exists(thread_id)
        logger.debug(
            "[chat][service] thread_switch requested=%s selected=%s",
            (thread_id or "").strip(),
            selected,
        )
        threads = self.store.list_threads()
        return {
            "threads": threads,
            "choices": self._thread_choices(threads),
            "history": self.store.load_messages(selected),
            "thread_id": selected,
            "status": self.chat_status(selected, "已切换"),
        }

    def rename_thread(self, thread_id: str, new_title: str) -> dict[str, Any]:
        selected = self._ensure_thread_exists(thread_id)
        title = (new_title or "").strip()
        logger.debug(
            "[chat][service] thread_rename requested=%s target=%s title_len=%s",
            (thread_id or "").strip(),
            selected,
            len(title),
        )
        if not title:
            return {
                "ok": False,
                "thread_id": selected,
                "status": self.chat_status(selected, "名称为空，未修改"),
                "reset_title": "",
            }
        try:
            self.store.rename_thread(selected, title=title, manual=True)
        except ValueError as error:
            return {
                "ok": False,
                "thread_id": selected,
                "status": self.chat_status(selected, f"重命名失败：{error}"),
                "reset_title": "",
            }
        threads = self.store.list_threads()
        return {
            "ok": True,
            "threads": threads,
            "choices": self._thread_choices(threads),
            "thread_id": selected,
            "status": self.chat_status(selected, "已重命名"),
            "reset_title": "",
        }

    def close_thread(self, thread_id: str) -> dict[str, Any]:
        selected = self._ensure_thread_exists(thread_id)
        logger.debug(
            "[chat][service] thread_close requested=%s selected=%s",
            (thread_id or "").strip(),
            selected,
        )
        self.close_agent(selected)
        self.store.delete_thread(selected)
        threads = self.store.list_threads()
        if not threads:
            created = self.store.create_thread()
            new_selected = str(created["thread_id"])
            history: list[dict[str, str]] = []
        else:
            new_selected = str(threads[0]["thread_id"])
            history = self.store.load_messages(new_selected)
        threads = self.store.list_threads()
        return {
            "threads": threads,
            "choices": self._thread_choices(threads),
            "history": history,
            "thread_id": new_selected,
            "status": self.chat_status(new_selected, "已关闭会话并删除记忆文件"),
        }

    def _generate_thread_title(self, user_input: str, assistant_output: str) -> str:
        conf = memory_conf.get("title_generation", {})
        max_len = int(conf.get("max_length", THREAD_TITLE_MAX_LEN))
        enabled = bool(conf.get("enabled", True))
        if not enabled:
            return (user_input or "新会话").strip()[:max_len] or "新会话"

        prompt = (
            "请根据以下一轮问答生成一个简洁中文会话标题。\n"
            f"要求：不超过{max_len}个字，不要标点结尾，不要引号。\n\n"
            f"用户：{(user_input or '')[:600]}\n"
            f"助手：{(assistant_output or '')[:1200]}\n\n"
            "只输出标题。"
        )
        try:
            response = _build_title_model().invoke(prompt)
            title = (getattr(response, "content", None) or str(response)).strip()
            title = title.replace("\n", " ").strip(" \"'“”")
            if title:
                return title[:max_len]
        except Exception as error:
            logger.warning("[chat] auto title generation failed: %s", error)
        fallback = (user_input or "新会话").strip() or "新会话"
        return fallback[:max_len]

    def stream_reply(
        self, thread_id: str, message: str, history: list[dict[str, str]] | None = None
    ) -> Iterator[ChatEvent]:
        selected = self._ensure_thread_exists(thread_id)
        prompt = (message or "").strip()
        if not prompt:
            yield ChatEvent(
                "error",
                {
                    "thread_id": selected,
                    "message": "请输入问题。",
                    "status": self.chat_status(selected, "请输入问题。"),
                },
            )
            return

        stream_lock = self._stream_lock_for(selected)
        if not stream_lock.acquire(blocking=False):
            yield ChatEvent(
                "error",
                {
                    "thread_id": selected,
                    "message": "当前会话已有请求正在执行，请稍后再试。",
                    "status": self.chat_status(selected, "请求仍在处理中"),
                },
            )
            return

        chunks: list[str] = []
        started_at = time.perf_counter()
        try:
            try:
                timeout_seconds = max(
                    int(memory_conf.get("chat_response_timeout_seconds", 180)),
                    1,
                )
            except Exception:
                timeout_seconds = 180

            self.store.append_message(selected, role="user", content=prompt)
            yield ChatEvent(
                "status",
                {
                    "phase": "start",
                    "thread_id": selected,
                    "message": prompt,
                    "status": self.chat_status(selected, "思考中..."),
                },
            )

            runtime_agent = self.get_agent(selected)
            logger.info(
                "[chat] request start thread=%s prompt_len=%s history_len=%s",
                selected,
                len(prompt),
                len(history or []),
            )

            done_payload: dict[str, Any] = {}
            for agent_event in runtime_agent.execute_events(prompt):
                elapsed_seconds = time.perf_counter() - started_at
                if elapsed_seconds > timeout_seconds:
                    logger.warning(
                        "[chat] response timeout thread=%s timeout_s=%s",
                        selected,
                        timeout_seconds,
                    )
                    raise TimeoutError(f"智能体响应超时（>{timeout_seconds}s）")

                if not isinstance(agent_event, AgentEvent):
                    text = str(agent_event or "")
                    if not text:
                        continue
                    chunks.append(text)
                    yield ChatEvent("token", {"thread_id": selected, "text": text})
                    continue

                if agent_event.type == "done":
                    done_payload = dict(agent_event.data)
                    continue

                text = str(agent_event.data.get("text") or "")
                if text:
                    chunks.append(text)

                payload = {"thread_id": selected, **agent_event.data}
                if agent_event.type in ("status", "tool", "token", "error"):
                    yield ChatEvent(agent_event.type, payload)

            final_answer = "".join(chunks).strip() or "⚠️ 未生成有效回复。"
            self.store.append_message(selected, role="assistant", content=final_answer)

            flags = self.store.get_flags(selected)
            title_changed = False
            threads: list[dict[str, Any]] = []
            if not flags.get("renamed", False) and not flags.get("auto_named", False):
                auto_title = self._generate_thread_title(prompt, final_answer)
                self.store.rename_thread(selected, title=auto_title, manual=False)
                threads = self.store.list_threads()
                title_changed = True

            logger.info(
                "[chat] request done thread=%s chars=%s title_changed=%s",
                selected,
                len(final_answer),
                title_changed,
            )
            yield ChatEvent(
                "done",
                {
                    "thread_id": selected,
                    "answer": final_answer,
                    "status": self.chat_status(
                        selected, "已自动命名" if title_changed else "回复完成"
                    ),
                    "threads": threads,
                    "choices": self._thread_choices(threads) if threads else [],
                    "title_changed": title_changed,
                    **done_payload,
                },
            )
        except TimeoutError as error:
            logger.warning(
                "[chat] request timeout thread=%s reason=%s", selected, error
            )
            error_message = "⚠️ 智能体响应超时，请稍后重试。"
            self.store.append_message(selected, role="assistant", content=error_message)
            yield ChatEvent(
                "error",
                {
                    "thread_id": selected,
                    "message": str(error),
                    "answer": error_message,
                    "status": self.chat_status(selected, "响应超时"),
                },
            )
        except Exception:
            logger.exception("[chat] request failed thread=%s", selected)
            error_message = "⚠️ 系统错误：智能体处理失败，请稍后重试。"
            self.store.append_message(selected, role="assistant", content=error_message)
            yield ChatEvent(
                "error",
                {
                    "thread_id": selected,
                    "message": "智能体处理失败",
                    "answer": error_message,
                    "status": self.chat_status(selected, "处理失败"),
                },
            )
        finally:
            stream_lock.release()
