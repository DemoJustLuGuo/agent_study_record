import gradio as gr

from app.runtime import (
    create_snapshot,
    ingest_web_urls,
    rollback_snapshot,
    sync_knowledge,
    upload_knowledge,
)


def build_knowledge_tab() -> None:
    with gr.TabItem("📦 知识库管理"):
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

        with gr.Group():
            gr.Markdown("### 🌐 网页链接入库")
            gr.Markdown("每行输入一个 HTTP/HTTPS 链接，点击后手动抓取并重建对应索引。")
            web_urls_input = gr.Textbox(
                label="网页链接",
                lines=5,
                placeholder="https://example.com/doc1\nhttps://example.com/doc2",
                show_label=False,
            )
            web_ingest_btn = gr.Button(
                "🌐 抓取网页并入库",
                variant="primary",
                size="lg",
            )
            web_ingest_result = gr.Markdown(
                "等待执行网页入库任务。",
                elem_classes=["markdown-body"],
            )

        web_ingest_btn.click(
            fn=ingest_web_urls,
            inputs=[web_urls_input, operator],
            outputs=[web_ingest_result],
            show_progress="full",
            api_name="knowledge_web_ingest",
        )

        gr.HTML('<div class="section-divider"></div>')

        with gr.Group():
            gr.Markdown("### ⚙️ 生命周期运维")
            gr.Markdown("管理向量数据库的快照、同步与回滚。")

            with gr.Row(equal_height=True):
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
