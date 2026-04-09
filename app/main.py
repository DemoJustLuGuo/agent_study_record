import os

from app.app_builder import build_app


def main() -> None:
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


if __name__ == "__main__":
    main()
