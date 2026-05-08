from pathlib import Path
from threading import Lock
from typing import Any

import gradio as gr

from app.chat_threads import ChatThreadStore
from rag.metrics import get_rag_metrics_markdown, reset_rag_metrics
from services.chat_service import ChatService
from services.knowledge_service import KnowledgeService
from services.rag_query_service import RagQueryService
from services.settings_service import (
    load_connection_defaults as service_load_connection_defaults,
    save_connection_settings as service_save_connection_settings,
)
from utils.log import logger

knowledge_base_service: Any | None = None
knowledge_base_lock = Lock()
rag_service: Any | None = None
rag_service_lock = Lock()
knowledge_service: KnowledgeService | None = None
knowledge_service_lock = Lock()
rag_query_service: RagQueryService | None = None
rag_query_service_lock = Lock()
chat_service: ChatService | None = None
chat_service_lock = Lock()
agent_config_lock = Lock()

THINKING_HTML = (
    '<div class="thinking-indicator">'
    '<span class="dot"></span>'
    '<span class="dot"></span>'
    '<span class="dot"></span>'
    "</div>"
)


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
    return get_chat_service().store


def get_chat_service() -> ChatService:
    global chat_service
    with chat_service_lock:
        if chat_service is None:
            chat_service = ChatService()
        return chat_service


def get_agent(thread_id: str) -> Any:
    return get_chat_service().get_agent(thread_id)


def _close_agent(thread_id: str) -> None:
    get_chat_service().close_agent(thread_id)


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


def _chat_status(thread_id: str, extra: str = "") -> str:
    return get_chat_service().chat_status(thread_id, extra)


def get_initial_chat_state_data() -> (
    tuple[list[tuple[str, str]], list[dict[str, str]], str, str]
):
    state = get_chat_service().get_initial_state_data()
    return state["choices"], state["history"], state["thread_id"], state["status"]


def init_chat_tab_state():
    choices, history, thread_id, status = get_initial_chat_state_data()
    return (
        gr.update(choices=choices, value=thread_id),
        history,
        thread_id,
        status,
    )


def create_chat_thread(current_thread_id: str):
    result = get_chat_service().create_thread(current_thread_id)
    return (
        gr.update(choices=result["choices"], value=result["thread_id"]),
        result["history"],
        result["thread_id"],
        result["status"],
    )


def switch_chat_thread(thread_id: str):
    result = get_chat_service().switch_thread(thread_id)
    return (
        gr.update(choices=result["choices"], value=result["thread_id"]),
        result["history"],
        result["thread_id"],
        result["status"],
    )


def rename_chat_thread(thread_id: str, new_title: str):
    result = get_chat_service().rename_thread(thread_id, new_title)
    if not result.get("ok"):
        return (
            gr.update(),
            result["thread_id"],
            result["status"],
            result.get("reset_title", ""),
        )
    return (
        gr.update(choices=result["choices"], value=result["thread_id"]),
        result["thread_id"],
        result["status"],
        result.get("reset_title", ""),
    )


def close_chat_thread(thread_id: str):
    result = get_chat_service().close_thread(thread_id)
    return (
        gr.update(choices=result["choices"], value=result["thread_id"]),
        result["history"],
        result["thread_id"],
        result["status"],
    )


def stream_thread_reply(
    thread_id: str, message: str, history: list[dict[str, str]] | None
):
    current_history = list(history or [])
    chunks: list[str] = []
    thinking_shown = False
    assistant_started = False
    selected = (thread_id or "").strip()

    for event in get_chat_service().stream_reply(thread_id, message, history):
        data = event.data
        selected = str(data.get("thread_id") or selected)

        if event.type == "status" and data.get("phase") == "start":
            current_history.append(
                {"role": "user", "content": str(data.get("message") or "")}
            )
            current_history.append({"role": "assistant", "content": ""})
            assistant_started = True
            yield current_history, "", str(data.get("status") or ""), gr.update()
            continue

        if event.type in ("status", "tool", "token"):
            raw_chunk = str(data.get("text") or "")
            if not raw_chunk:
                continue
            chunks.append(raw_chunk)
            all_thinking = all(
                c.strip().startswith("[THINK]") for c in chunks if c.strip()
            )
            full_text = "".join(chunks)
            if assistant_started:
                if all_thinking:
                    thinking_shown = True
                    current_history[-1][
                        "content"
                    ] = f"{THINKING_HTML}\n\n**▌ 思考中...**\n\n{full_text}"
                else:
                    current_history[-1]["content"] = normalize_markdown_layout(
                        full_text
                    )
            yield current_history, "", _chat_status(selected, "思考中..."), gr.update()
            continue

        if event.type == "done":
            final_answer = normalize_markdown_layout(
                str(data.get("answer") or "".join(chunks))
            ).strip()
            if not final_answer:
                final_answer = "⚠️ 未生成有效回复。"
            if assistant_started:
                current_history[-1]["content"] = final_answer
            selector_update = gr.update()
            if data.get("title_changed"):
                selector_update = gr.update(
                    choices=data.get("choices", []), value=selected
                )
            logger.info(
                "[chat] ui stream done thread=%s chunks=%s thinking_phase=%s",
                selected,
                len(chunks),
                thinking_shown,
            )
            yield (
                current_history,
                "",
                str(data.get("status") or _chat_status(selected, "回复完成")),
                selector_update,
            )
            continue

        if event.type == "error":
            status = str(data.get("status") or _chat_status(selected, "处理失败"))
            answer = str(data.get("answer") or "")
            if assistant_started and answer:
                current_history[-1]["content"] = answer
            yield current_history, "", status, gr.update()
            return


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
