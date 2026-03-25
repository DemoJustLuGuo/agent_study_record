import os
import re
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

import gradio as gr
import yaml

from utils.path_tools import get_abs_path

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
AGENT_CONFIG_PATH = get_abs_path("config/agent.yml")


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


def _load_connection_defaults() -> tuple[str, str, str]:
    config_data = _read_agent_config()
    base_url = str(config_data.get("openai_base_url", "")).strip()
    key_value = str(config_data.get("OPENAI_API_KEY", "")).strip()

    if _looks_like_env_var(key_value):
        status = (
            "当前 `OPENAI_API_KEY` 配置为环境变量名，"
            "请在下方填写真实密钥后自动写入 `config/agent.yml`。"
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
        f"✅ 已自动保存到 `config/agent.yml`："
        f"API 地址 `{base_url}`，API Key `{_mask_secret(api_key)}`。"
    )

def _load_app_css() -> str:
    css_path = Path(__file__).with_name("ui.css")
    try:
        return css_path.read_text(encoding="utf-8")
    except Exception:
        # UI stylesheet is optional; failing to read should not break the app.
        return ""

THINKING_HTML = (
    '<div class="thinking-indicator">'
    '<span class="dot"></span>'
    '<span class="dot"></span>'
    '<span class="dot"></span>'
    "</div>"
)


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
        content = item.get("content", "").strip()
        metadata = item.get("metadata", {})
        source = metadata.get("source", "未知来源")
        lines.append(f"**[{i}]** `{source}`\n")
        lines.append(f"> {content}\n")
    return "\n".join(lines)


def stream_agent_reply(message: str, history: list[dict[str, str]]):
    prompt = (message or "").strip()
    if not prompt:
        yield "请输入问题。"
        return

    chunks: list[str] = []
    thinking_shown = False

    try:
        runtime_agent = get_agent()
        for chunk in runtime_agent.execute_stream(prompt):
            text = chunk.strip()
            if not text:
                continue

            chunks.append(chunk)

            # 所有 chunk 都是 [THINK] 前缀时 → 仍在思考阶段，显示加载动画
            all_thinking = all(
                c.strip().startswith("[THINK]") for c in chunks if c.strip()
            )

            if all_thinking:
                thinking_shown = True
                yield f"{THINKING_HTML}\n\n**▌ 思考中...**\n\n" + "".join(chunks)
            else:
                yield "".join(chunks)
    except Exception:
        yield "⚠️ 系统错误：智能体处理失败，请稍后重试。"


def rag_query(prompt: str):
    query = (prompt or "").strip()
    if not query:
        return "请输入问题。", ""

    try:
        result = get_rag_service().answer_with_references(query)
    except Exception:
        return "⚠️ 系统错误：RAG 查询失败，请稍后重试。", ""

    answer = result.get("answer", "")
    references = _render_references(result.get("references", []))
    refs_md = _references_to_markdown(references)
    return answer, refs_md


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
        result = get_knowledge_base_service().sync_removed_sources()
    except Exception:
        return {"error": "系统错误：同步失败。"}
    return result


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


def build_app() -> gr.Blocks:
    default_base_url, default_api_key, connection_status_text = _load_connection_defaults()

    with gr.Blocks(
        title="通信智能体工作台", css=_load_app_css(), theme=gr.themes.Base()
    ) as demo:
        # ===== Header =====
        gr.HTML(
            '<div class="header-bar">'
            '<div class="header-title-wrap">'
            '<h1>📡 通信智能体工作台 </h1>'
            '<div class="header-subtitle">LangChain ReAct Agent · RAG 检索增强 · ChromaDB 知识底座</div>'
            "</div>"
            '<span class="status-badge online">在线运行</span>'
            "</div>"
        )

        with gr.Group(elem_classes=["card"]):
            gr.Markdown("### 🔐 OpenAI 连接设置")
            gr.Markdown(
                "在主页直接填写 OpenAI 兼容 API 地址与密钥。输入框失焦后将自动写入 `config/agent.yml`。"
            )
            with gr.Row():
                openai_base_url_input = gr.Textbox(
                    label="OpenAI API 地址",
                    value=default_base_url,
                    placeholder="例如：https://api.openai.com/v1",
                )
                openai_api_key_input = gr.Textbox(
                    label="OpenAI API 密钥",
                    value=default_api_key,
                    placeholder="sk-...",
                    type="password",
                )
            connection_status = gr.Markdown(connection_status_text)

        openai_base_url_input.change(
            fn=save_connection_settings,
            inputs=[openai_base_url_input, openai_api_key_input],
            outputs=[connection_status],
            show_progress="hidden",
        )
        openai_api_key_input.change(
            fn=save_connection_settings,
            inputs=[openai_base_url_input, openai_api_key_input],
            outputs=[connection_status],
            show_progress="hidden",
        )

        # ===== Main Tabs =====
        with gr.Tabs():
            # ===== Tab 1: Agent Chat =====
            with gr.TabItem("💬 智能体对话"):
                gr.Markdown(
                    "支持 Markdown 输出：标题、代码块、表格、引用和链接都会自动渲染。",
                    elem_classes=["markdown-body"],
                )
                gr.ChatInterface(
                    fn=stream_agent_reply,
                    type="messages",
                    title="",
                    description="",
                    chatbot=gr.Chatbot(
                        type="messages",
                        label="对话",
                        height=520,
                        show_label=False,
                        layout="bubble",
                        bubble_full_width=False,
                        avatar_images=(None, None),
                        render_markdown=True,
                        sanitize_html=True,
                        show_copy_button=True,
                        show_copy_all_button=True,
                        line_breaks=True,
                        placeholder="👋 你好！我是通信领域工程智能体，请输入你的问题。",
                    ),
                    textbox=gr.Textbox(
                        placeholder="请输入通信系统问题...（如：解释 OFDM 原理）",
                        lines=1,
                        max_lines=5,
                        show_label=False,
                        container=False,
                        autofocus=True,
                        submit_btn="发送",
                        stop_btn="停止",
                        html_attributes={"enterkeyhint": "send"},
                    ),
                    examples=[
                        "解释 OFDM 的基本原理，并给出与单载波系统的差异。",
                        "用 Python 估算 BPSK 在 AWGN 下 BER 随 Eb/N0 的变化趋势。",
                        "LTE 切换失败的常见原因有哪些？",
                        "5G NR 的峰值速率如何计算？",
                    ],
                )

            # ===== Tab 2: RAG Query =====
            with gr.TabItem("🔍 在线 RAG"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=1):
                        gr.Markdown("### 📖 知识库检索")
                        gr.Markdown("直接向知识库提问，基于向量相似度检索并生成回答。")
                        rag_input = gr.Textbox(
                            label="问题",
                            placeholder="输入需要检索知识库的问题",
                            lines=3,
                            show_label=False,
                        )
                        rag_btn = gr.Button(
                            "🚀 检索并回答", variant="primary", size="lg"
                        )

                    with gr.Column(scale=2):
                        rag_answer = gr.Markdown(
                            label="回答",
                            show_label=True,
                            container=True,
                            elem_classes=["markdown-body"],
                        )
                        rag_refs = gr.Markdown(
                            label="命中参考片段",
                            show_label=True,
                            container=True,
                            elem_classes=["markdown-body"],
                        )

                rag_btn.click(
                    fn=rag_query,
                    inputs=[rag_input],
                    outputs=[rag_answer, rag_refs],
                    api_name="rag_query",
                )

            # ===== Tab 3: Knowledge Base =====
            with gr.TabItem("📦 知识库管理"):
                # Upload Section
                with gr.Group():
                    gr.Markdown("### 📤 上传知识文件")
                    with gr.Row():
                        with gr.Column(scale=3):
                            upload_file = gr.File(
                                label="选择文件",
                                file_types=[".txt"],
                                type="filepath",
                                container=False,
                            )
                        with gr.Column(scale=1):
                            operator = gr.Textbox(
                                label="操作人",
                                value="gradio",
                                container=False,
                            )
                        with gr.Column(scale=1):
                            upload_btn = gr.Button(
                                "📤 上传入库",
                                variant="primary",
                                size="lg",
                            )
                    upload_result = gr.Textbox(
                        label="上传结果",
                        interactive=False,
                        show_label=False,
                        container=False,
                    )

                upload_btn.click(
                    fn=upload_knowledge,
                    inputs=[upload_file, operator],
                    outputs=[upload_result],
                    api_name="knowledge_upload",
                )

                gr.HTML('<div class="section-divider"></div>')

                # Lifecycle Section
                with gr.Group():
                    gr.Markdown("### ⚙️ 生命周期运维")
                    gr.Markdown("管理向量数据库的快照、同步与回滚。")

                    with gr.Row(equal_height=True):
                        # Sync Card
                        with gr.Column():
                            with gr.Group(elem_classes=["card"]):
                                gr.Markdown("#### 🔄 同步清理")
                                gr.Markdown("删除已移除源文件对应的向量数据。")
                                sync_btn = gr.Button(
                                    "🔄 同步失效源文件",
                                    variant="secondary",
                                    size="lg",
                                )
                                sync_result = gr.JSON(label="同步结果")

                        # Snapshot Card
                        with gr.Column():
                            with gr.Group(elem_classes=["card"]):
                                gr.Markdown("📸 创建快照")
                                gr.Markdown("为当前向量库状态创建可回滚的快照。")
                                snapshot_tag = gr.Textbox(
                                    label="快照标签",
                                    placeholder="可选，如 release_v1",
                                    show_label=False,
                                )
                                snapshot_btn = gr.Button(
                                    "📸 创建快照",
                                    variant="secondary",
                                    size="lg",
                                )
                                snapshot_result = gr.JSON(label="快照结果")

                        # Rollback Card
                        with gr.Column():
                            with gr.Group(elem_classes=["card"]):
                                gr.Markdown("⏪ 回滚快照")
                                gr.Markdown("将向量库恢复到指定快照状态。")
                                rollback_name = gr.Textbox(
                                    label="快照名称",
                                    placeholder="必填，如 20260321_120000",
                                    show_label=False,
                                )
                                rollback_btn = gr.Button(
                                    "⏪ 回滚快照",
                                    variant="stop",
                                    size="lg",
                                )
                                rollback_result = gr.JSON(label="回滚结果")

                sync_btn.click(
                    fn=sync_knowledge,
                    inputs=None,
                    outputs=[sync_result],
                    api_name="knowledge_sync",
                )
                snapshot_btn.click(
                    fn=create_snapshot,
                    inputs=[snapshot_tag],
                    outputs=[snapshot_result],
                    api_name="knowledge_snapshot",
                )
                rollback_btn.click(
                    fn=rollback_snapshot,
                    inputs=[rollback_name],
                    outputs=[rollback_result],
                    api_name="knowledge_rollback",
                )

        # ===== Footer =====
        gr.HTML(
            '<div style="text-align:center; padding:16px; color:var(--text-muted); font-size:0.8rem;">'
            "Powered by LangChain · LangGraph · Gradio · ChromaDB"
            "</div>"
        )

    return demo


if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "7860"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"

    app = build_app()
    app.queue(default_concurrency_limit=8)
    app.launch(
        server_name=host,
        server_port=port,
        show_api=True,
        debug=debug,
    )
