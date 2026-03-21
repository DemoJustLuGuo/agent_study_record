import os
from pathlib import Path
from threading import Lock
from typing import Any

import gradio as gr

from agent.react_agent import ReactAgent
from rag.knowledge_base import KnowledgeBaseService
from rag.rag_service import RAGSummarizeService


agent = None
agent_lock = Lock()
knowledge_base_service = None
knowledge_base_lock = Lock()
rag_service = None
rag_service_lock = Lock()


def get_agent() -> ReactAgent:
    global agent
    if agent is None:
        with agent_lock:
            if agent is None:
                agent = ReactAgent()
    return agent


def get_knowledge_base_service() -> KnowledgeBaseService:
    global knowledge_base_service
    if knowledge_base_service is None:
        with knowledge_base_lock:
            if knowledge_base_service is None:
                knowledge_base_service = KnowledgeBaseService()
    return knowledge_base_service


def get_rag_service() -> RAGSummarizeService:
    global rag_service
    if rag_service is None:
        with rag_service_lock:
            if rag_service is None:
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


def stream_agent_reply(message: str, history: list[dict[str, str]]):
    prompt = (message or "").strip()
    if not prompt:
        yield "请输入问题。"
        return

    chunks: list[str] = []
    try:
        runtime_agent = get_agent()
        for chunk in runtime_agent.execute_stream(prompt):
            chunks.append(chunk)
            yield "".join(chunks)
    except Exception:
        yield "系统错误：智能体处理失败，请稍后重试。"


def rag_query(prompt: str):
    query = (prompt or "").strip()
    if not query:
        return "请输入问题。", []

    try:
        result = get_rag_service().answer_with_references(query)
    except Exception:
        return "系统错误：RAG 查询失败，请稍后重试。", []

    return result.get("answer", ""), _render_references(result.get("references", []))


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
        result = get_knowledge_base_service().upload_by_str(text, source.name, operator=user)
    except Exception:
        return "系统错误：知识写入失败。"

    return f"上传完成：{result}"


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
    with gr.Blocks(title="通信智能体工作台") as demo:
        gr.Markdown("# 通信智能体工作台")
        gr.Markdown("基于 Gradio 的统一入口：Agent 对话、在线 RAG、知识库管理。")

        with gr.Tabs():
            with gr.TabItem("智能体对话"):
                gr.ChatInterface(
                    fn=stream_agent_reply,
                    type="messages",
                    title="Agent Chat",
                    description="直接对接 ReactAgent.execute_stream()，支持流式回答。",
                    textbox=gr.Textbox(placeholder="请输入通信系统问题...", lines=3),
                    examples=[
                        "解释 OFDM 的基本原理，并给出与单载波系统的差异。",
                        "用 Python 估算 BPSK 在 AWGN 下 BER 随 Eb/N0 的变化趋势。",
                    ],
                )

            with gr.TabItem("在线 RAG 直答"):
                rag_input = gr.Textbox(label="问题", placeholder="输入需要检索知识库的问题", lines=3)
                rag_btn = gr.Button("检索并回答", variant="primary")
                rag_answer = gr.Markdown(label="回答")
                rag_refs = gr.JSON(label="命中片段（已脱敏）")
                rag_btn.click(fn=rag_query, inputs=[rag_input], outputs=[rag_answer, rag_refs], api_name="rag_query")

            with gr.TabItem("知识库管理"):
                upload_file = gr.File(label="上传文本", file_types=[".txt"], type="filepath")
                operator = gr.Textbox(label="操作人", value="gradio")
                upload_btn = gr.Button("上传入库", variant="primary")
                upload_result = gr.Textbox(label="上传结果", interactive=False)
                upload_btn.click(
                    fn=upload_knowledge,
                    inputs=[upload_file, operator],
                    outputs=[upload_result],
                    api_name="knowledge_upload",
                )

                gr.Markdown("### 生命周期运维")
                with gr.Row():
                    sync_btn = gr.Button("同步失效源文件")
                    sync_result = gr.JSON(label="同步结果")
                sync_btn.click(fn=sync_knowledge, inputs=None, outputs=[sync_result], api_name="knowledge_sync")

                with gr.Row():
                    snapshot_tag = gr.Textbox(label="快照标签", placeholder="可选")
                    snapshot_btn = gr.Button("创建快照")
                    snapshot_result = gr.JSON(label="快照结果")
                snapshot_btn.click(
                    fn=create_snapshot,
                    inputs=[snapshot_tag],
                    outputs=[snapshot_result],
                    api_name="knowledge_snapshot",
                )

                with gr.Row():
                    rollback_name = gr.Textbox(label="快照名称", placeholder="必填，例如 20260321_120000_release")
                    rollback_btn = gr.Button("回滚快照", variant="stop")
                    rollback_result = gr.JSON(label="回滚结果")
                rollback_btn.click(
                    fn=rollback_snapshot,
                    inputs=[rollback_name],
                    outputs=[rollback_result],
                    api_name="knowledge_rollback",
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
