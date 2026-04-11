import subprocess
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from utils.log import logger
from utils.path_tools import get_abs_path

TOOL_TIMEOUT_SECONDS = 30
TOOL_OUTPUT_MAX_CHARS = 10000


def truncate_output(text: str) -> str:
    if len(text) <= TOOL_OUTPUT_MAX_CHARS:
        return text
    return text[:TOOL_OUTPUT_MAX_CHARS] + "\n...[输出过长，已截断]"


def format_tool_failure(tool_name: str, reason: str, solution: str) -> str:
    return "\n".join(
        [
            f"【失败】{tool_name}调用失败",
            f"原因：{(reason or '未知错误').strip()}",
            f"解决方案：{(solution or '请检查工具依赖与输入参数后重试。').strip()}",
        ]
    )


def run_subprocess(command: list[str], tool_name: str) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=get_abs_path(""),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TOOL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return format_tool_failure(
            tool_name=tool_name,
            reason=f"执行超时（>{TOOL_TIMEOUT_SECONDS}s）",
            solution="请缩小输入规模、减少命令复杂度，或调大超时阈值后重试。",
        )
    except Exception as exc:
        logger.error(f"{tool_name}执行失败: {str(exc)}", exc_info=True)
        return format_tool_failure(
            tool_name=tool_name,
            reason=f"执行异常: {str(exc)}",
            solution="请检查运行环境、命令参数与依赖安装状态后重试。",
        )

    parts: list[str] = [
        f"tool={tool_name}",
        f"exit_code={completed.returncode}",
    ]

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if stdout:
        parts.append("stdout:\n" + stdout)
    if stderr:
        parts.append("stderr:\n" + stderr)
    if not stdout and not stderr:
        parts.append("stdout/stderr为空")

    return truncate_output("\n".join(parts))


def load_text_from_url(url: str, timeout: int) -> Optional[str]:
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            encoding = "utf-8"
            if "charset=" in content_type:
                encoding = (
                    content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
                )

            return response.read().decode(encoding, errors="replace")
    except URLError as exc:
        logger.warning(f"联网请求失败: {str(exc)}")
    except Exception as exc:
        logger.warning(f"联网请求异常: {str(exc)}")
    return None
