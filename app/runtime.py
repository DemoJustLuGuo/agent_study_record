import re
import time
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

from langchain_openai import ChatOpenAI
import gradio as gr

from app.chat_threads import ChatThreadStore, THREAD_TITLE_MAX_LEN
from rag.metrics import get_rag_metrics_markdown, reset_rag_metrics
from services.knowledge_service import KnowledgeService
from services.rag_query_service import RagQueryService
from services.settings_service import (
    load_connection_defaults as service_load_connection_defaults,
    read_agent_config,
    resolve_secret,
    save_connection_settings as service_save_connection_settings,
    write_agent_config,
)
from utils.config_handler import memory_conf
from utils.path_tools import get_abs_path
from utils.log import logger

if TYPE_CHECKING:
    from agent.react_agent import ReactAgent
    from rag.knowledge_base import KnowledgeBaseService
    from rag.rag_service import RAGSummarizeService


agent: "ReactAgent | None" = None
agent_lock = Lock()
thread_store: "ChatThreadStore | None" = None
thread_store_lock = Lock()
thread_agents: dict[str, "ReactAgent"] = {}
thread_agents_lock = Lock()
knowledge_base_service: "KnowledgeBaseService | None" = None
knowledge_base_lock = Lock()
rag_service: "RAGSummarizeService | None" = None
rag_service_lock = Lock()
knowledge_service: KnowledgeService | None = None
knowledge_service_lock = Lock()
rag_query_service: RagQueryService | None = None
rag_query_service_lock = Lock()
agent_config_lock = Lock()

THINKING_HTML = (
    '<div class="thinking-indicator">'
    '<span class="dot"></span>'
    '<span class="dot"></span>'
    '<span class="dot"></span>'
    "</div>"
)


def _looks_like_env_var(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", (value or "").strip()))


def _read_agent_config() -> dict[str, Any]:
    return read_agent_config()


def _write_agent_config(config_data: dict[str, Any]) -> None:
    write_agent_config(config_data)


def _mask_secret(secret: str) -> str:
    value = (secret or "").strip()
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def load_connection_defaults() -> tuple[str, str, str]:
    return service_load_connection_defaults()


def save_connection_settings(openai_base_url: str, openai_api_key: str) -> str:
    with agent_config_lock:
        return service_save_connection_settings(openai_base_url, openai_api_key)


def normalize_markdown_layout(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if "\\n" in normalized and "\n" not in normalized:
        normalized = normalized.replace("\\n", "\n")
    return normalized


def get_thread_store() -> ChatThreadStore:
    global thread_store
    with thread_store_lock:
        if thread_store is None:
            thread_store = ChatThreadStore()
        return thread_store


def _thread_choices(threads: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [
        (f"{item.get('title', item.get('thread_id', '会话'))}", item["thread_id"])
        for item in threads
    ]


def _ensure_thread_exists(thread_id: str | None = None) -> str:
    store = get_thread_store()
    all_ids = set(store.list_thread_ids())
    text = (thread_id or "").strip()
    if text and text in all_ids:
        return text
    created = store.create_thread()
    return str(created["thread_id"])


def get_agent(thread_id: str) -> "ReactAgent":
    with thread_agents_lock:
        cached = thread_agents.get(thread_id)
        if cached is not None:
            return cached
        from agent.react_agent import ReactAgent

        db_path = get_abs_path(f"memory_db/{thread_id}.db")
        runtime_agent = ReactAgent(thread_id=thread_id, db_path=db_path)
        thread_agents[thread_id] = runtime_agent
        return runtime_agent


def _close_agent(thread_id: str) -> None:
    with thread_agents_lock:
        runtime_agent = thread_agents.pop(thread_id, None)
    if runtime_agent is None:
        return
    try:
        runtime_agent.close()
    except Exception:
        logger.debug("[chat] close agent failed thread=%s", thread_id)


def get_knowledge_base_service() -> "KnowledgeBaseService":
    global knowledge_base_service
    with knowledge_base_lock:
        if knowledge_base_service is None:
            from rag.knowledge_base import KnowledgeBaseService

            knowledge_base_service = KnowledgeBaseService()
        return knowledge_base_service


def get_rag_service() -> "RAGSummarizeService":
    global rag_service
    with rag_service_lock:
        if rag_service is None:
            from rag.rag_service import RAGSummarizeService

            rag_service = RAGSummarizeService()
        return rag_service


def get_knowledge_service() -> KnowledgeService:
    global knowledge_service
    with knowledge_service_lock:
        if knowledge_service is None:
            knowledge_service = KnowledgeService(get_knowledge_base_service())
        return knowledge_service


def get_rag_query_service() -> RagQueryService:
    global rag_query_service
    with rag_query_service_lock:
        if rag_query_service is None:
            rag_query_service = RagQueryService(get_rag_service())
        return rag_query_service


def _mask_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    masked = dict(metadata or {})
    source = str(masked.get("source") or "").strip()
    if source:
        masked["source"] = Path(source).name
    return masked


def _render_references(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rendered: list[dict[str, Any]] = []
    for item in references:
        rendered.append(
            {
                "content": item.get("content", ""),
                "metadata": _mask_metadata(item.get("metadata", {})),
            }
        )
    return rendered


def _references_to_markdown(references: list[dict[str, Any]]) -> str:
    if not references:
        return "> 暂无匹配的参考片段。"
    lines = ["### 📚 命中参考片段\n"]
    for i, item in enumerate(references, 1):
        content = normalize_markdown_layout(item.get("content", "").strip())
        if len(content) > 420:
            content = content[:420] + "...（已截断）"
        quoted_content = (
            "\n".join(f"> {line}" for line in content.splitlines() if line.strip())
            or "> （空片段）"
        )
        metadata = item.get("metadata", {})
        source = metadata.get("source", "未知来源")
        source_type = metadata.get("source_type", "unknown")
        lines.append(f"#### [{i}] `{source}`\n")
        lines.append(f"- 类型：`{source_type}`\n")
        lines.append(f"{quoted_content}\n")
    return "\n".join(lines)


def _answer_to_markdown(answer: str, reference_count: int) -> str:
    body = normalize_markdown_layout((answer or "").strip()) or "未生成有效回答。"
    return "\n".join(
        [
            "### 🧠 检索回答",
            f"> 命中参考片段：**{reference_count}**",
            "",
            body,
        ]
    )


def _retrieval_debug_to_markdown(debug_info: dict[str, Any]) -> str:
    if not debug_info:
        return ""
    return "\n".join(
        [
            "",
            "---",
            "#### 检索调试信息",
            f"- 策略：`{debug_info.get('strategy', 'unknown')}`",
            f"- 向量命中：`{debug_info.get('vector_hits', 0)}`",
            f"- 关键词命中：`{debug_info.get('keyword_hits', 0)}`",
            f"- 候选数：`{debug_info.get('candidate_count', 0)}`",
            f"- 目标返回：`{debug_info.get('final_k', 0)}`",
            f"- 检索耗时：`{debug_info.get('elapsed_ms', 0)} ms`",
        ]
    )


def prepare_rag_loading(prompt: str) -> tuple[str, str]:
    if not (prompt or "").strip():
        return "请输入问题。", ""
    return "### 🔎 正在搜索...\n请稍候，正在检索知识库并生成回答。", ""


def _parse_web_urls(urls_text: str) -> list[str]:
    raw = (urls_text or "").replace(",", "\n")
    urls = [line.strip() for line in raw.splitlines() if line.strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def _web_ingest_result_to_markdown(result: dict[str, Any]) -> str:
    details = result.get("details", [])
    lines = [
        "### 🌐 网页入库结果",
        f"- 总数：`{result.get('total', 0)}`",
        f"- 新增：`{result.get('added', 0)}`",
        f"- 更新：`{result.get('updated', 0)}`",
        f"- 跳过：`{result.get('skipped', 0)}`",
        f"- 失败：`{result.get('failed', 0)}`",
        "",
    ]
    if details:
        lines.append("#### 详情")
        for item in details:
            url = item.get("url", "-")
            status = item.get("status", "-")
            reason = item.get("reason", "")
            reason_text = f"（{reason}）" if reason else ""
            lines.append(f"- `{status}` {url} {reason_text}")
    return "\n".join(lines)


def _resolve_secret(value: str) -> str:
    return resolve_secret(value)


def _build_title_model() -> ChatOpenAI:
    conf = memory_conf.get("summarizer_model", {})
    model_name = str(conf.get("model_name", "")).strip() or "Pro/MiniMaxAI/MiniMax-M2.5"
    temperature = float(conf.get("temperature", 0.2))
    kwargs: dict[str, Any] = {"model": model_name, "temperature": temperature}
    base_url = str(conf.get("base_url", "")).strip()
    api_key = _resolve_secret(str(conf.get("api_key", "")).strip())
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    return ChatOpenAI(**kwargs)


def _generate_thread_title(user_input: str, assistant_output: str) -> str:
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
    fallback = (user_input or "新会话").strip()
    if not fallback:
        fallback = "新会话"
    return fallback[:max_len]


def _chat_status(thread_id: str, extra: str = "") -> str:
    title = get_thread_store().get_title(thread_id)
    base = f"当前会话：`{title}`（{thread_id}）"
    if extra:
        return f"{base} · {extra}"
    return base


def get_initial_chat_state_data() -> (
    tuple[list[tuple[str, str]], list[dict[str, str]], str, str]
):
    store = get_thread_store()
    threads = store.list_threads()
    if not threads:
        created = store.create_thread()
        thread_id = str(created["thread_id"])
    else:
        thread_id = str(threads[0]["thread_id"])
    threads = store.list_threads()
    history = store.load_messages(thread_id)
    return _thread_choices(threads), history, thread_id, _chat_status(thread_id)


def init_chat_tab_state():
    choices, history, thread_id, status = get_initial_chat_state_data()
    return (
        gr.update(choices=choices, value=thread_id),
        history,
        thread_id,
        status,
    )


def create_chat_thread(current_thread_id: str):
    store = get_thread_store()
    created = store.create_thread()
    thread_id = str(created["thread_id"])
    logger.debug(
        "[chat][ui] thread_create current=%s created=%s",
        (current_thread_id or "").strip(),
        thread_id,
    )
    threads = store.list_threads()
    return (
        gr.update(choices=_thread_choices(threads), value=thread_id),
        [],
        thread_id,
        _chat_status(thread_id, "已创建新会话"),
    )


def switch_chat_thread(thread_id: str):
    selected = _ensure_thread_exists(thread_id)
    logger.debug(
        "[chat][ui] thread_switch requested=%s selected=%s",
        (thread_id or "").strip(),
        selected,
    )
    history = get_thread_store().load_messages(selected)
    threads = get_thread_store().list_threads()
    return (
        gr.update(choices=_thread_choices(threads), value=selected),
        history,
        selected,
        _chat_status(selected, "已切换"),
    )


def rename_chat_thread(thread_id: str, new_title: str):
    selected = _ensure_thread_exists(thread_id)
    title = (new_title or "").strip()
    logger.debug(
        "[chat][ui] thread_rename requested=%s target=%s title_len=%s",
        (thread_id or "").strip(),
        selected,
        len(title),
    )
    if not title:
        return (
            gr.update(),
            selected,
            _chat_status(selected, "名称为空，未修改"),
            "",
        )
    try:
        get_thread_store().rename_thread(selected, title=title, manual=True)
    except ValueError as error:
        return (
            gr.update(),
            selected,
            _chat_status(selected, f"重命名失败：{error}"),
            "",
        )
    threads = get_thread_store().list_threads()
    return (
        gr.update(choices=_thread_choices(threads), value=selected),
        selected,
        _chat_status(selected, "已重命名"),
        "",
    )


def close_chat_thread(thread_id: str):
    store = get_thread_store()
    selected = _ensure_thread_exists(thread_id)
    logger.debug(
        "[chat][ui] thread_close requested=%s selected=%s",
        (thread_id or "").strip(),
        selected,
    )
    _close_agent(selected)
    store.delete_thread(selected)
    threads = store.list_threads()
    if not threads:
        created = store.create_thread()
        new_selected = str(created["thread_id"])
        history: list[dict[str, str]] = []
    else:
        new_selected = str(threads[0]["thread_id"])
        history = store.load_messages(new_selected)
    threads = store.list_threads()
    return (
        gr.update(choices=_thread_choices(threads), value=new_selected),
        history,
        new_selected,
        _chat_status(new_selected, "已关闭会话并删除记忆文件"),
    )


def stream_thread_reply(
    thread_id: str, message: str, history: list[dict[str, str]] | None
):
    selected = _ensure_thread_exists(thread_id)
    prompt = (message or "").strip()
    current_history = list(history or [])
    if not prompt:
        yield current_history, "", _chat_status(selected, "请输入问题。"), gr.update()
        return

    store = get_thread_store()
    current_history.append({"role": "user", "content": prompt})
    current_history.append({"role": "assistant", "content": ""})
    yield current_history, "", _chat_status(selected, "思考中..."), gr.update()

    chunks: list[str] = []
    thinking_shown = False
    try:
        timeout_seconds = max(
            int(memory_conf.get("chat_response_timeout_seconds", 180)),
            1,
        )
    except Exception:
        timeout_seconds = 180
    started_at = time.perf_counter()
    try:
        store.append_message(selected, role="user", content=prompt)
        runtime_agent = get_agent(selected)
        logger.info(
            "[chat] request start thread=%s prompt_len=%s history_len=%s",
            selected,
            len(prompt),
            len(current_history),
        )
        for chunk in runtime_agent.execute_stream(prompt):
            elapsed_seconds = time.perf_counter() - started_at
            if elapsed_seconds > timeout_seconds:
                logger.warning(
                    "[chat] response timeout thread=%s timeout_s=%s",
                    selected,
                    timeout_seconds,
                )
                raise TimeoutError(f"智能体响应超时（>{timeout_seconds}s）")
            if chunk is None:
                continue
            raw_chunk = str(chunk)
            if raw_chunk == "":
                continue

            chunks.append(raw_chunk)
            all_thinking = all(
                c.strip().startswith("[THINK]") for c in chunks if c.strip()
            )
            full_text = "".join(chunks)
            if all_thinking:
                thinking_shown = True
                current_history[-1][
                    "content"
                ] = f"{THINKING_HTML}\n\n**▌ 思考中...**\n\n{full_text}"
            else:
                current_history[-1]["content"] = normalize_markdown_layout(full_text)
            yield current_history, "", _chat_status(selected, "思考中..."), gr.update()

        final_answer = normalize_markdown_layout("".join(chunks)).strip()
        if not final_answer:
            final_answer = "⚠️ 未生成有效回复。"
        current_history[-1]["content"] = final_answer
        store.append_message(selected, role="assistant", content=final_answer)

        flags = store.get_flags(selected)
        selector_update = gr.update()
        status = _chat_status(selected, "回复完成")
        if not flags.get("renamed", False) and not flags.get("auto_named", False):
            auto_title = _generate_thread_title(prompt, final_answer)
            store.rename_thread(selected, title=auto_title, manual=False)
            threads = store.list_threads()
            selector_update = gr.update(
                choices=_thread_choices(threads), value=selected
            )
            status = _chat_status(selected, "已自动命名")

        logger.info(
            "[chat] request done thread=%s chunks=%s thinking_phase=%s",
            selected,
            len(chunks),
            thinking_shown,
        )
        yield current_history, "", status, selector_update
    except TimeoutError as error:
        logger.warning("[chat] request timeout thread=%s reason=%s", selected, error)
        error_message = "⚠️ 智能体响应超时，请稍后重试。"
        current_history[-1]["content"] = error_message
        store.append_message(selected, role="assistant", content=error_message)
        yield current_history, "", _chat_status(selected, "响应超时"), gr.update()
    except Exception:
        logger.exception("[chat] request failed thread=%s", selected)
        error_message = "⚠️ 系统错误：智能体处理失败，请稍后重试。"
        current_history[-1]["content"] = error_message
        store.append_message(selected, role="assistant", content=error_message)
        yield current_history, "", _chat_status(selected, "处理失败"), gr.update()


def rag_query(prompt: str):
    result = get_rag_query_service().answer_with_references(prompt)
    if result.get("error"):
        return str(result.get("error")), ""

    answer = _answer_to_markdown(
        result.get("answer", ""),
        len(result.get("references", [])),
    )
    answer += _retrieval_debug_to_markdown(result.get("retrieval_debug", {}))
    references = _render_references(result.get("references", []))
    refs_md = _references_to_markdown(references)
    return answer, refs_md


def refresh_rag_metrics_panel() -> str:
    return get_rag_metrics_markdown()


def reset_rag_metrics_panel() -> str:
    reset_message = reset_rag_metrics()
    return "\n".join(["### 📈 在线 RAG 指标", f"> {reset_message}"])


def ingest_web_urls(urls_text: str, operator: str):
    result = get_knowledge_service().ingest_web_urls(urls_text, operator)
    if result.get("error"):
        return str(result.get("error"))
    return _web_ingest_result_to_markdown(result)


def upload_knowledge(file_path: str, operator: str):
    return get_knowledge_service().upload_file(file_path, operator=operator)


def sync_knowledge():
    return get_knowledge_service().sync_removed_sources()


def create_snapshot(tag: str):
    return get_knowledge_service().create_snapshot(tag)


def rollback_snapshot(snapshot_name: str, confirm_name: str):
    return get_knowledge_service().rollback_snapshot(snapshot_name, confirm_name)
