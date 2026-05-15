import os

from app.app_builder import build_app


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "7860"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"
    show_api = _env_flag("GRADIO_SHOW_API")

    app = build_app()
    app.queue(default_concurrency_limit=8)
    app.launch(
        server_name=host,
        server_port=port,
        show_api=show_api,
        debug=debug,
    )


if __name__ == "__main__":
    main()
