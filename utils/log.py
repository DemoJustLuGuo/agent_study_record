import logging
import os
import sys
from datetime import datetime

from utils.path_tools import get_abs_path

LOG_ROOT = get_abs_path("logs")
os.makedirs(LOG_ROOT, exist_ok=True)

DEFAULT_LOG_FORMAT = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)


def _utf8_stream(stream):
    """
    Ensure console stream writes in UTF-8; fallback gracefully if wrapping fails.
    """
    try:
        if getattr(stream, "encoding", "").lower() == "utf-8":
            return stream
        if hasattr(stream, "buffer"):
            return open(
                stream.buffer.fileno(),
                mode="w",
                encoding="utf-8",
                buffering=1,
                errors="replace",
                closefd=False,
            )
        return open(
            stream.fileno(),
            mode="w",
            encoding="utf-8",
            buffering=1,
            errors="replace",
            closefd=False,
        )
    except Exception:
        return stream


def _enable_windows_utf8_console():
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def _reconfigure_std_streams():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace", newline=None)
            except Exception:
                pass


def _resolve_level_name(level_name: str) -> int | None:
    raw = str(level_name or "").strip().upper()
    if not raw:
        return None
    mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.CRITICAL,
    }
    return mapping.get(raw)


def _level_floor_from_env() -> int | None:
    return _resolve_level_name(os.environ.get("LOG_LEVEL", ""))


def get_logger(
    name: str = "agent-lab",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    log_file: str | None = None,
) -> logging.Logger:
    _enable_windows_utf8_console()
    _reconfigure_std_streams()

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    level_floor = _level_floor_from_env()
    if level_floor is not None:
        console_level = max(console_level, level_floor)
        file_level = max(file_level, level_floor)

    console_handler = logging.StreamHandler(_utf8_stream(sys.stdout))
    console_handler.setLevel(console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)
    logger.addHandler(console_handler)

    if not log_file:
        log_file = os.path.join(
            LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.log"
        )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)
    logger.addHandler(file_handler)

    return logger


logger = get_logger()


if __name__ == "__main__":
    logger.debug("debug log for self-test")
    logger.info("info log for self-test")
    logger.warning("warn log for self-test")
    logger.error("error log for self-test")
    logger.critical("critical log for self-test")
