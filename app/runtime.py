import os
import re
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

import yaml

from rag.metrics import get_rag_metrics_markdown, record_rag_metric, reset_rag_metrics
from utils.path_tools import get_abs_path
from utils.log import logger

if TYPE_CHECKING:
    from agent.react_agent import ReactAgent
    from rag.knowledge_base import KnowledgeBaseService
    from rag.rag_service import RAGSummarizeService


agent: "ReactAgent | None" = None
agent_lock = Lock()
knowledge_base_service: "KnowledgeBaseService | None" = None
knowledge_base_lock = Lock()
rag_service: "RAGSummarizeService | None" = None
rag_service_lock = Lock()
agent_config_lock = Lock()
AGENT_CONFIG_PATH = get_abs_path("model/config/agent.yml")

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
    try:
        with open(AGENT_CONFIG_PATH, "r", encoding="utf-8") as file_obj:
            data = yaml.safe_load(file_obj) or {}
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}


def _write_agent_config(config_data: dict[str, Any]) -> None:
    config_dir = os.path.dirname(AGENT_CONFIG_PATH)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    with open(AGENT_CONFIG_PATH, "w", encoding="utf-8") as file_obj:
        yaml.safe_dump(config_data, file_obj, allow_unicode=True, sort_keys=False)


def _mask_secret(secret: str) -> str:
    value = (secret or "").strip()
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def load_connection_defaults() -> tuple[str, str, str]:
    config_data = _read_agent_config()
    base_url = str(config_data.get("openai_base_url", "")).strip()
    key_value = str(config_data.get("OPENAI_API_KEY", "")).strip()

    if _looks_like_env_var(key_value):
        status = (
            "当前 `OPENAI_API_KEY` 配置为环境变量名，"
            "请在下方填写真实密钥后自动写入 `model/config/agent.yml`。"
        )
        return base_url, "", status

    if key_value:
        status = (
            f"已读取现有配置：API 地址 `{base_url}`，"
            f"API Key `{_mask_secret(key_value)}`。"
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

    with agent_config_lock:
        config_data = _read_agent_config()
        config_data["openai_base_url"] = base_url
        config_data["OPENAI_API_KEY"] = api_key
        _write_agent_config(config_data)

    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["SILICONFLOW_API_KEY"] = api_key
    return (
        f"✅ 已自动保存到 `model/config/agent.yml`："
        f"API 地址 `{base_url}`，API Key `{_mask_secret(api_key)}`。"
    )


def normalize_markdown_layout(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if "\\n" in normalized and "\n" not in normalized:
        normalized = normalized.replace("\\n", "\n")
    return normalized


def get_agent() -> "ReactAgent":
    global agent
    if agent is None:
        with agent_lock:
            if agent is None:
                from agent.react_agent import ReactAgent

                agent = ReactAgent()
    return agent


def get_knowledge_base_service() -> "KnowledgeBaseService":
    global knowledge_base_service
    if knowledge_base_service is None:
        with knowledge_base_lock:
            if knowledge_base_service is None:
                from rag.knowledge_base import KnowledgeBaseService

                knowledge_base_service = KnowledgeBaseService()
    return knowledge_base_service


def get_rag_service() -> "RAGSummarizeService":
    global rag_service
    if rag_service is None:
        with rag_service_lock:
            if rag_service is None:
                from rag.rag_service import RAGSummarizeService

                rag_service = RAGSummarizeService()
    return rag_service


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
        quoted_content = "\n".join(
            f"> {line}" for line in content.splitlines() if line.strip()
        ) or "> （空片段）"
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


def stream_agent_reply(message: str, history: list[dict[str, str]]):
    prompt = (message or "").strip()
    if not prompt:
        yield "请输入问题。"
        return

    chunks: list[str] = []
    thinking_shown = False

    try:
        logger.info(
            "[chat] request start prompt_len=%s history_len=%s",
            len(prompt),
            len(history or []),
        )
        runtime_agent = get_agent()
        for chunk in runtime_agent.execute_stream(prompt):
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
                yield f"{THINKING_HTML}\n\n**▌ 思考中...**\n\n" + full_text
            else:
                yield normalize_markdown_layout(full_text)
        if chunks:
            yield normalize_markdown_layout("".join(chunks))
        logger.info(
            "[chat] request done chunks=%s thinking_phase=%s",
            len(chunks),
            thinking_shown,
        )
    except Exception:
        logger.exception("[chat] request failed")
        yield "⚠️ 系统错误：智能体处理失败，请稍后重试。"


def rag_query(prompt: str):
    query = (prompt or "").strip()
    if not query:
        return "请输入问题。", ""

    try:
        logger.info("[rag] query start len=%s", len(query))
        result = get_rag_service().answer_with_references(query)
    except Exception:
        logger.exception("[rag] query failed")
        record_rag_metric(
            {
                "ok": False,
                "strategy": "error",
                "reference_count": 0,
                "candidate_count": 0,
                "retrieval_ms": 0,
                "rerank_ms": 0,
                "llm_ms": 0,
                "total_ms": 0,
            }
        )
        return "⚠️ 系统错误：RAG 查询失败，请稍后重试。", ""

    answer = _answer_to_markdown(
        result.get("answer", ""),
        len(result.get("references", [])),
    )
    answer += _retrieval_debug_to_markdown(result.get("retrieval_debug", {}))
    references = _render_references(result.get("references", []))
    refs_md = _references_to_markdown(references)
    metrics = result.get("metrics", {})
    record_rag_metric(
        {
            "ok": True,
            "strategy": metrics.get("strategy", "unknown"),
            "reference_count": metrics.get("reference_count", len(references)),
            "candidate_count": metrics.get("candidate_count", 0),
            "retrieval_ms": metrics.get("retrieval_ms", 0),
            "rerank_ms": metrics.get("rerank_ms", 0),
            "llm_ms": metrics.get("llm_ms", 0),
            "total_ms": metrics.get("total_ms", 0),
        }
    )
    logger.info("[rag] query done refs=%s", len(references))
    return answer, refs_md


def refresh_rag_metrics_panel() -> str:
    return get_rag_metrics_markdown()


def reset_rag_metrics_panel() -> str:
    reset_message = reset_rag_metrics()
    return "\n".join(["### 📈 在线 RAG 指标", f"> {reset_message}"])


def ingest_web_urls(urls_text: str, operator: str):
    urls = _parse_web_urls(urls_text)
    if not urls:
        return "请先输入至少一个 HTTP/HTTPS 链接。"

    user = (operator or "gradio").strip() or "gradio"
    try:
        logger.info("[rag] web ingest start urls=%s operator=%s", len(urls), user)
        result = get_knowledge_base_service().upsert_web_urls(urls=urls, operator=user)
        logger.info(
            "[rag] web ingest done total=%s added=%s updated=%s skipped=%s failed=%s",
            result.get("total", 0),
            result.get("added", 0),
            result.get("updated", 0),
            result.get("skipped", 0),
            result.get("failed", 0),
        )
    except Exception:
        logger.exception("[rag] web ingest failed")
        return "⚠️ 系统错误：网页抓取/入库失败。"
    return _web_ingest_result_to_markdown(result)


def upload_knowledge(file_path: str, operator: str):
    if not file_path:
        return "请先上传 .txt 文件。"

    source = Path(file_path)
    if source.suffix.lower() != ".txt":
        return "仅支持 .txt 文件。"

    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "文件编码错误：请使用 UTF-8 编码。"
    except Exception:
        return "系统错误：读取上传文件失败。"

    if not text.strip():
        return "文件内容为空。"

    user = (operator or "gradio").strip() or "gradio"
    try:
        result = get_knowledge_base_service().upload_by_str(
            text, source.name, operator=user
        )
    except Exception:
        return "系统错误：知识写入失败。"

    return f"✅ {result}"


def sync_knowledge():
    try:
        return get_knowledge_base_service().sync_removed_sources()
    except Exception:
        return {"error": "系统错误：同步失败。"}


def create_snapshot(tag: str):
    try:
        name = get_knowledge_base_service().create_snapshot(tag=(tag or "").strip())
    except Exception:
        return {"error": "系统错误：快照创建失败。"}
    return {"snapshot": name}


def rollback_snapshot(snapshot_name: str):
    name = (snapshot_name or "").strip()
    if not name:
        return {"error": "请填写快照名称。"}

    try:
        restored = get_knowledge_base_service().rollback_snapshot(name)
    except FileNotFoundError:
        return {"error": "快照不存在。"}
    except Exception:
        return {"error": "系统错误：回滚失败。"}
    return {"snapshot": restored, "result": "ok"}
