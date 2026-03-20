from typing import Any

from langchain_core.tools import tool

from agent.tools.modules.shared import truncate_output
from utils.log import logger

try:
    from langchain_experimental.tools.python.tool import PythonREPLTool
except Exception:  # pragma: no cover
    PythonREPLTool = None  # type: ignore[assignment]

try:
    import matlab.engine as matlab_engine
except Exception:  # pragma: no cover
    matlab_engine = None  # type: ignore[assignment]


_python_repl_tool: Any = None
_matlab_engine_session: Any = None


def _get_python_repl_tool() -> Any:
    global _python_repl_tool
    if _python_repl_tool is not None:
        return _python_repl_tool

    if PythonREPLTool is None:
        raise RuntimeError(
            "未安装PythonREPLTool依赖，请先安装 langchain-experimental（例如：pip install langchain-experimental）。"
        )

    _python_repl_tool = PythonREPLTool()
    return _python_repl_tool


def _get_matlab_engine() -> Any:
    global _matlab_engine_session
    if _matlab_engine_session is not None:
        return _matlab_engine_session

    if matlab_engine is None:
        raise RuntimeError(
            "未安装matlabengine模块，请先在MATLAB支持的Python环境中安装 matlabengine 后重试。"
        )

    try:
        _matlab_engine_session = matlab_engine.start_matlab()
    except Exception as exc:
        raise RuntimeError(f"启动MATLAB Engine失败: {str(exc)}") from exc

    return _matlab_engine_session


def _normalize_result(prefix:str, result:Any) -> str:
    text = "" if result is None else str(result).strip()
    if not text:
        return f"【成功】{prefix}执行完成（无输出）"
    return truncate_output(text)

@tool(description="执行Python代码并返回执行结果，适用于通信算法快速计算、验证与仿真")
def python(code:str) -> str:
    code = (code or "").strip()
    if not code:
        return "【失败】python代码为空"

    try:
        python_tool = _get_python_repl_tool()
        try:
            result = python_tool.run(code)
        except Exception:
            result = python_tool.invoke(code)
        return _normalize_result("python", result)
    except Exception as exc:
        logger.error(f"python执行失败: {str(exc)}", exc_info=True)
        return f"【失败】python执行异常: {str(exc)}"


@tool(description="执行MATLAB代码并返回执行结果，基于matlabengine模块")
def matlab(code:str) -> str:
    code = (code or "").strip()
    if not code:
        return "【失败】matlab代码为空"

    try:
        engine = _get_matlab_engine()
        result = engine.evalc(code, nargout=1)
        return _normalize_result("matlab", result)
    except Exception as exc:
        logger.error(f"matlab执行失败: {str(exc)}", exc_info=True)
        return f"【失败】matlab执行异常: {str(exc)}"
