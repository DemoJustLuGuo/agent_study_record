import gradio as gr

from app.runtime import stream_agent_reply


def build_chat_tab() -> None:
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
