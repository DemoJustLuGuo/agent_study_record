import gradio as gr

from app.runtime import (
    prepare_rag_loading,
    rag_query,
    refresh_rag_metrics_panel,
    reset_rag_metrics_panel,
)


def build_rag_tab() -> None:
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
                rag_btn = gr.Button("🚀 检索并回答", variant="primary", size="lg")

            with gr.Column(scale=2):
                rag_answer = gr.Markdown(
                    label="回答",
                    show_label=True,
                    container=True,
                    elem_classes=["markdown-body"],
                    line_breaks=True,
                )
                rag_refs = gr.Markdown(
                    label="命中参考片段",
                    show_label=True,
                    container=True,
                    elem_classes=["markdown-body"],
                    line_breaks=True,
                )

        rag_btn.click(
            fn=prepare_rag_loading,
            inputs=[rag_input],
            outputs=[rag_answer, rag_refs],
            show_progress="hidden",
            api_name=False,
        ).then(
            fn=rag_query,
            inputs=[rag_input],
            outputs=[rag_answer, rag_refs],
            api_name=False,
        )

        gr.HTML('<div class="section-divider"></div>')
        with gr.Group():
            gr.Markdown("### 📊 检索运行指标")
            gr.Markdown("展示当前会话窗口内的 RAG 检索运行统计。")
            with gr.Row():
                metrics_refresh_btn = gr.Button("🔄 刷新指标", variant="secondary")
                metrics_reset_btn = gr.Button("🧹 重置指标", variant="secondary")
            metrics_panel = gr.Markdown(
                "### 📈 在线 RAG 指标\n> 暂无运行数据。",
                elem_classes=["markdown-body"],
                line_breaks=True,
            )

        metrics_refresh_btn.click(
            fn=refresh_rag_metrics_panel,
            inputs=None,
            outputs=[metrics_panel],
            show_progress="hidden",
            api_name=False,
        )
        metrics_reset_btn.click(
            fn=reset_rag_metrics_panel,
            inputs=None,
            outputs=[metrics_panel],
            show_progress="hidden",
            api_name=False,
        )
