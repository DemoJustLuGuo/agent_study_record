import gradio as gr

from app.runtime import (
    close_chat_thread,
    create_chat_thread,
    get_initial_chat_state_data,
    rename_chat_thread,
    stream_thread_reply,
    switch_chat_thread,
)


def build_chat_tab() -> None:
    with gr.TabItem("💬 智能体对话"):
        gr.Markdown("支持多会话线程聊天，关闭会话后会删除对应短期记忆数据库。")
        initial_choices, initial_history, initial_thread_id, initial_status = (
            get_initial_chat_state_data()
        )
        thread_state = gr.State(value=initial_thread_id)

        with gr.Row():
            with gr.Column(scale=3, min_width=220):
                thread_selector = gr.Radio(
                    label="会话列表",
                    choices=initial_choices,
                    value=initial_thread_id,
                    interactive=True,
                )
                with gr.Row():
                    create_btn = gr.Button("新建会话", variant="secondary")
                    close_btn = gr.Button("关闭会话", variant="stop")
                rename_input = gr.Textbox(
                    label="重命名会话（<=50字）",
                    placeholder="输入后点击“保存名称”",
                    lines=1,
                )
                rename_btn = gr.Button("保存名称", variant="secondary")
                chat_status = gr.Markdown(initial_status)

            with gr.Column(scale=10):
                chatbot = gr.Chatbot(
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
                    value=initial_history,
                )
                msg_input = gr.Textbox(
                    placeholder="请输入通信系统问题...（如：解释 OFDM 原理）",
                    lines=1,
                    max_lines=5,
                    show_label=False,
                    container=False,
                    autofocus=True,
                    submit_btn="发送",
                    stop_btn=False,
                    html_attributes={"enterkeyhint": "send"},
                )

        gr.Examples(
            examples=[
                "解释 OFDM 的基本原理，并给出与单载波系统的差异。",
                "用 Python 估算 BPSK 在 AWGN 下 BER 随 Eb/N0 的变化趋势。",
                "LTE 切换失败的常见原因有哪些？",
                "5G NR 的峰值速率如何计算？",
            ],
            inputs=[msg_input],
        )

        thread_selector.change(
            fn=switch_chat_thread,
            inputs=[thread_selector],
            outputs=[thread_selector, chatbot, thread_state, chat_status],
            api_name=False,
        )

        create_btn.click(
            fn=create_chat_thread,
            inputs=[thread_state],
            outputs=[thread_selector, chatbot, thread_state, chat_status],
            api_name=False,
        )

        close_btn.click(
            fn=close_chat_thread,
            inputs=[thread_state],
            outputs=[thread_selector, chatbot, thread_state, chat_status],
            api_name=False,
        )

        rename_btn.click(
            fn=rename_chat_thread,
            inputs=[thread_state, rename_input],
            outputs=[thread_selector, thread_state, chat_status, rename_input],
            api_name=False,
        )

        msg_input.submit(
            fn=stream_thread_reply,
            inputs=[thread_state, msg_input, chatbot],
            outputs=[chatbot, msg_input, chat_status, thread_selector],
            api_name=False,
        )
