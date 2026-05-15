import gradio as gr

from app.runtime import save_connection_settings


def build_connection_panel(
    default_base_url: str,
    default_api_key: str,
    connection_status_text: str,
) -> None:
    with gr.Group(elem_classes=["card"]):
        gr.Markdown("### 🔐 OpenAI 连接设置")
        gr.Markdown(
            "在主页直接填写 OpenAI 兼容 API 地址与密钥。输入框失焦后将自动写入 `model/config/agent.yml`。"
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
        api_name=False,
    )
    openai_api_key_input.change(
        fn=save_connection_settings,
        inputs=[openai_base_url_input, openai_api_key_input],
        outputs=[connection_status],
        show_progress="hidden",
        api_name=False,
    )
