from __future__ import annotations

import json
import os
import time
from datetime import datetime
from threading import Lock
from typing import Any, Callable

from langchain.agents import AgentState
from langchain.agents.middleware import (
    ModelRequest,
    ModelResponse,
    after_model,
    before_model,
    dynamic_prompt,
    wrap_model_call,
    wrap_tool_call,
)
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from utils.log import LOG_ROOT, logger
from utils.prompt_loader import load_report_prompt, load_system_prompt

TRUNCATE_USER_MODEL_LOG = 200
TRUNCATE_TOOL_ARGS_LOG = 800
TRUNCATE_TOOL_RESULT_LOG = 1200
TRACE_DIR = os.path.join(LOG_ROOT, "traces")
os.makedirs(TRACE_DIR, exist_ok=True)
_TOOL_EVENTS: dict[str, list[dict[str, Any]]] = {}
_TOOL_EVENTS_LOCK = Lock()


def _trace_id(runtime: Runtime | None) -> str:
    try:
        return str(runtime.context.get("trace_id") or "trace-missing")
    except Exception:
        return "trace-missing"


def _log_prefix(runtime: Runtime | None) -> str:
    return f"[trace={_trace_id(runtime)}] "


def _preview_text(text: str, limit: int) -> str:
    text = (text or "").replace("\n", " ")
    if len(text) > limit:
        return text[:limit] + f"...(truncated,len={len(text)})"
    return text


def _extract_message_content(msg: Any) -> str:
    try:
        if isinstance(msg, BaseMessage):
            content = msg.content
        elif isinstance(msg, dict):
            content = msg.get("content", "")
        else:
            content = getattr(msg, "content", "") or str(msg)
        return str(content)
    except Exception:
        return "<unprintable>"


def _preview_message(msg: Any, limit: int = TRUNCATE_USER_MODEL_LOG) -> str:
    return _preview_text(_extract_message_content(msg), limit)


def _message_snapshot_for_logs(
    messages: list[Any], limit: int = 8
) -> list[dict[str, Any]]:
    snapshot = []
    for msg in messages[-limit:]:
        content = _extract_message_content(msg)
        snapshot.append(
            {
                "type": type(msg).__name__,
                "role": getattr(msg, "type", getattr(msg, "role", "")),
                "preview": _preview_text(content, TRUNCATE_USER_MODEL_LOG),
                "len": len(content),
            }
        )
    return snapshot


def _message_snapshot_for_trace(messages: list[Any]) -> list[dict[str, Any]]:
    snapshot = []
    for msg in messages:
        snapshot.append(
            {
                "type": type(msg).__name__,
                "role": getattr(msg, "type", getattr(msg, "role", "")),
                "content": _extract_message_content(msg),
            }
        )
    return snapshot


def _result_messages(response: Any) -> list[Any]:
    """
    Normalize model response to a list of messages.
    Accepts ModelResponse, dict, or raw list.
    """
    if hasattr(response, "result"):
        return getattr(response, "result") or []
    if isinstance(response, dict):
        return response.get("result", []) or response.get("messages", []) or []
    if isinstance(response, list):
        return response
    return []


def _extract_tool_result_text(result: ToolMessage | Command) -> str:
    if isinstance(result, ToolMessage):
        return _extract_message_content(result)
    if hasattr(result, "content"):
        return _extract_message_content(result)
    return str(result)


def _extract_python_or_matlab_code(tool_name: str, args_payload: Any) -> str:
    if tool_name not in ("python", "matlab"):
        return ""
    if isinstance(args_payload, dict):
        code = args_payload.get("code", "")
        return str(code or "")
    return str(args_payload or "")


def sanitize_tool_args_preview(tool_name: str, args_payload: Any) -> str:
    if isinstance(args_payload, dict):
        safe_payload = dict(args_payload)
        if tool_name in ("python", "matlab") and "code" in safe_payload:
            code_text = str(safe_payload.get("code") or "")
            safe_payload["code"] = f"<redacted code,len={len(code_text)}>"
        return _preview_text(str(safe_payload), limit=TRUNCATE_TOOL_ARGS_LOG)
    if tool_name in ("python", "matlab"):
        text = str(args_payload or "")
        return f"<redacted code,len={len(text)}>"
    return _preview_text(str(args_payload), limit=TRUNCATE_TOOL_ARGS_LOG)


def _latest_user_message_preview(messages: list[Any]) -> str:
    for msg in reversed(messages):
        role = str(getattr(msg, "type", getattr(msg, "role", ""))).lower()
        if role in ("human", "user"):
            return _preview_text(_extract_message_content(msg), TRUNCATE_USER_MODEL_LOG)
    if not messages:
        return ""
    return _preview_text(
        _extract_message_content(messages[-1]), TRUNCATE_USER_MODEL_LOG
    )


def _write_trace(runtime: Runtime | None, event: str, **payload: Any) -> None:
    trace_id = _trace_id(runtime)
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "trace_id": trace_id,
        "event": event,
        **payload,
    }
    path = os.path.join(TRACE_DIR, f"{trace_id}.jsonl")
    try:
        with open(path, "a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        logger.debug(f"{_log_prefix(runtime)}trace file write failed: {exc}")


def _push_tool_event(
    runtime: Runtime | None, phase: str, tool: str, **payload: Any
) -> None:
    trace_id = _trace_id(runtime)
    if not trace_id:
        return

    with _TOOL_EVENTS_LOCK:
        queue = _TOOL_EVENTS.setdefault(trace_id, [])
        queue.append({"phase": phase, "tool": tool, **payload})
        if len(queue) > 100:
            del queue[:-100]


def pop_tool_events(trace_id: str) -> list[dict[str, Any]]:
    if not trace_id:
        return []

    with _TOOL_EVENTS_LOCK:
        queue = _TOOL_EVENTS.get(trace_id, [])
        if not queue:
            return []
        events = list(queue)
        queue.clear()
        return events


def clear_tool_events(trace_id: str) -> None:
    if not trace_id:
        return
    with _TOOL_EVENTS_LOCK:
        _TOOL_EVENTS.pop(trace_id, None)


@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """
    Log tool invocation with timing; set report flag when fill_context_for_report is called.
    Also emit a JSONL trace for later replay.
    """
    start = time.perf_counter()
    tool_name = request.tool_call["name"]
    args_payload = request.tool_call.get("args")
    args_text = str(args_payload)
    args_preview = sanitize_tool_args_preview(tool_name, args_payload)
    code_text = _extract_python_or_matlab_code(tool_name, args_payload)
    code_preview = _preview_text(code_text, limit=TRUNCATE_TOOL_ARGS_LOG)
    trace_prefix = _log_prefix(request.runtime)

    logger.debug(
        f"{trace_prefix}[tool] start name={tool_name} args={args_preview}"
        + (f" code_preview={code_preview}" if code_text else "")
    )
    _push_tool_event(request.runtime, "start", tool_name, args_preview=args_preview)
    _write_trace(
        request.runtime,
        "tool_start",
        tool=tool_name,
        args=args_text,
        code=code_text,
    )

    try:
        result = handler(request)
        elapsed = (time.perf_counter() - start) * 1000

        result_text = _extract_tool_result_text(result)
        result_preview = _preview_text(result_text, limit=TRUNCATE_TOOL_RESULT_LOG)

        logger.debug(
            f"{trace_prefix}[tool] done name={tool_name} elapsed_ms={elapsed:.1f} result={result_preview}"
        )
        _write_trace(
            request.runtime,
            "tool_end",
            tool=tool_name,
            elapsed_ms=elapsed,
            result=result_text,
        )
        _push_tool_event(
            request.runtime,
            "end",
            tool_name,
            elapsed_ms=elapsed,
            result_preview=result_preview,
        )
        if "执行超时" in result_text or "timeout" in result_text.lower():
            logger.warning(
                f"{trace_prefix}[tool] timeout name={tool_name} elapsed_ms={elapsed:.1f}"
            )
            _write_trace(
                request.runtime,
                "tool_timeout",
                tool=tool_name,
                elapsed_ms=elapsed,
                result=result_text,
            )

        if tool_name == "fill_context_for_report":
            request.runtime.context["report"] = True
            logger.debug(
                f"{trace_prefix}[tool] set report=True by fill_context_for_report"
            )

        return result
    except Exception as exc:  # pragma: no cover
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception(
            f"{trace_prefix}[tool] fail name={tool_name} elapsed_ms={elapsed:.1f} error={exc}"
        )
        _write_trace(
            request.runtime,
            "tool_error",
            tool=tool_name,
            elapsed_ms=elapsed,
            error=str(exc),
        )
        _push_tool_event(
            request.runtime,
            "error",
            tool_name,
            elapsed_ms=elapsed,
            error_preview=_preview_text(str(exc), limit=TRUNCATE_TOOL_RESULT_LOG),
        )
        raise


@before_model
def log_before_model(state: AgentState, runtime: Runtime):
    """
    Record model call context to debug 'no response' cases.
    Emits both human-friendly logs and structured trace.
    """
    messages = state.get("messages", []) or []
    trace_prefix = _log_prefix(runtime)
    logger.info(
        f"{trace_prefix}[model] preparing call messages={len(messages)} report={runtime.context.get('report', False)}"
    )
    if messages:
        last = messages[-1]
        logger.info(
            "%s[model] input last_type=%s input_preview=%s",
            trace_prefix,
            type(last).__name__,
            _preview_message(last, limit=TRUNCATE_USER_MODEL_LOG),
        )
    _write_trace(
        runtime,
        "model_prepare",
        messages=len(messages),
        input_messages=_message_snapshot_for_trace(messages),
        report=runtime.context.get("report", False),
    )
    return None


@wrap_model_call
def log_model_call(
    request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
):
    """Wrap the LLM call to time it and capture the full prompt/response outline."""
    start = time.perf_counter()
    trace_prefix = _log_prefix(request.runtime)
    model_name = (
        getattr(request.model, "model_name", None)
        or getattr(request.model, "model", None)
        or type(request.model).__name__
    )
    model_temperature = getattr(request.model, "temperature", None)
    model_base_url = (
        getattr(request.model, "openai_api_base", None)
        or getattr(request.model, "base_url", None)
        or ""
    )
    tool_names = []
    for tool_obj in request.tools or []:
        tool_name = getattr(tool_obj, "name", None) or getattr(
            tool_obj, "__name__", None
        )
        if tool_name:
            tool_names.append(str(tool_name))

    prompt_preview = _latest_user_message_preview(request.messages or [])
    logger.info(
        "%s[model] start name=%s messages=%s tools=%s report=%s prompt_preview=%s params={temperature:%s,base_url:%s,tools:%s}",
        trace_prefix,
        model_name,
        len(request.messages),
        len(request.tools or []),
        request.runtime.context.get("report", False),
        prompt_preview,
        model_temperature,
        model_base_url,
        tool_names,
    )
    _write_trace(
        request.runtime,
        "model_start",
        model=model_name,
        model_params={
            "temperature": model_temperature,
            "base_url": model_base_url,
            "tools": tool_names,
        },
        messages=len(request.messages),
        input_messages=_message_snapshot_for_trace(request.messages),
        report=request.runtime.context.get("report", False),
    )

    try:
        response = handler(request)
        elapsed = (time.perf_counter() - start) * 1000
        outputs = _result_messages(response)
        output_preview = _preview_text(
            "\n".join(_extract_message_content(msg) for msg in outputs),
            TRUNCATE_USER_MODEL_LOG,
        )

        logger.info(
            f"{trace_prefix}[model] done name={model_name} elapsed_ms={elapsed:.1f} outputs={len(outputs)} output_preview={output_preview}"
        )
        _write_trace(
            request.runtime,
            "model_end",
            model=model_name,
            elapsed_ms=elapsed,
            outputs=len(outputs),
            output_messages=_message_snapshot_for_trace(outputs),
        )
        return response
    except Exception as exc:  # pragma: no cover
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception(
            f"{trace_prefix}[model] fail name={model_name} elapsed_ms={elapsed:.1f} error={exc}"
        )
        _write_trace(
            request.runtime,
            "model_error",
            model=model_name,
            elapsed_ms=elapsed,
            error=str(exc),
        )
        raise


@after_model
def log_after_model(response: ModelResponse, runtime: Runtime):
    """Log the final messages returned by the model (post tool/plan)."""
    trace_prefix = _log_prefix(runtime)
    outputs = _result_messages(response)
    logger.debug(
        "%s[model] after_model outputs=%s preview=%s",
        trace_prefix,
        len(outputs),
        _message_snapshot_for_logs(outputs)[:2],
    )
    _write_trace(
        runtime,
        "model_after",
        outputs=len(outputs),
        output_messages=_message_snapshot_for_trace(outputs),
    )
    return response


@dynamic_prompt
def report_prompt_switch(request: ModelRequest):
    """Switch prompt based on report flag in runtime context and log the decision."""
    is_report = request.runtime.context.get("report", False)
    trace_prefix = _log_prefix(request.runtime)
    if is_report:
        logger.info(f"{trace_prefix}[prompt] using report prompt")
        _write_trace(request.runtime, "prompt_switch", to="report")
        return load_report_prompt()
    logger.info(f"{trace_prefix}[prompt] using system prompt")
    _write_trace(request.runtime, "prompt_switch", to="system")
    return load_system_prompt()
