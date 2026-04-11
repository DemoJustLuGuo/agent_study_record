from pathlib import Path

import gradio as gr

from app.runtime import load_connection_defaults
from app.ui.chat_tab import build_chat_tab
from app.ui.connection_panel import build_connection_panel
from app.ui.knowledge_tab import build_knowledge_tab
from app.ui.rag_tab import build_rag_tab


def _load_app_css() -> str:
    css_path = Path(__file__).with_name("ui.css")
    try:
        return css_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def build_app() -> gr.Blocks:
    default_base_url, default_api_key, connection_status_text = (
        load_connection_defaults()
    )

    with gr.Blocks(
        title="通信智能体工作台", css=_load_app_css(), theme=gr.themes.Base()
    ) as demo:
        gr.HTML(
            '<div class="header-bar">'
            '<div class="header-title-wrap">'
            "<h1>📡 通信智能体工作台 </h1>"
            '<div class="header-subtitle">LangChain ReAct Agent · RAG 检索增强 · ChromaDB 知识底座</div>'
            "</div>"
            '<span class="status-badge online">在线运行</span>'
            "</div>"
        )

        build_connection_panel(
            default_base_url=default_base_url,
            default_api_key=default_api_key,
            connection_status_text=connection_status_text,
        )

        with gr.Tabs():
            build_chat_tab()
            build_rag_tab()
            build_knowledge_tab()

        gr.HTML(
            '<div style="text-align:center; padding:16px; color:var(--text-muted); font-size:0.8rem;">'
            "Powered by LangChain · LangGraph · Gradio · ChromaDB"
            "</div>"
        )

    return demo
