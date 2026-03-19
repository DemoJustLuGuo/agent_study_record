from __future__ import annotations

import json
import os
import time
from datetime import datetime
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

TRUNCATE_PREVIEW = 400
TRUNCATE_RESULT = 800
TRACE_MESSAGE_LIMIT = 8
TRACE_DIR = os.path.join(LOG_ROOT, "traces")
os.makedirs(TRACE_DIR, exist_ok=True)


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
        return text[:limit] + "...(truncated)"
    return text


def _preview_message(msg: Any, limit: int = TRUNCATE_PREVIEW) -> str:
    try:
        if isinstance(msg, BaseMessage):
            content = msg.content
        elif isinstance(msg, dict):
            content = msg.get("content", "")
        else:
            content = getattr(msg, "content", "") or str(msg)
        return _preview_text(str(content), limit)
    except Exception:
        return "<unprintable>"


def _message_snapshot(messages: list[Any], limit: int = TRACE_MESSAGE_LIMIT) -> list[dict[str, Any]]:
    snapshot = []
    for msg in messages[-limit:]:
        snapshot.append(
            {
                "type": type(msg).__name__,
                "role": getattr(msg, "type", getattr(msg, "role", "")),
                "preview": _preview_message(msg),
                "len": len(getattr(msg, "content", "") or str(getattr(msg, "content", ""))),
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
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        logger.debug(f"{_log_prefix(runtime)}trace file write failed: {exc}")


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
    args_preview = _preview_text(str(request.tool_call.get("args")), limit=TRUNCATE_PREVIEW)
    trace_prefix = _log_prefix(request.runtime)

    logger.info(f"{trace_prefix}[tool] start name={tool_name} args_preview={args_preview}")
    _write_trace(
        request.runtime,
        "tool_start",
        tool=tool_name,
        args_preview=args_preview,
    )

    try:
        result = handler(request)
        elapsed = (time.perf_counter() - start) * 1000

        preview = ""
        if isinstance(result, ToolMessage):
            preview = _preview_message(result, limit=TRUNCATE_RESULT)
        elif hasattr(result, "content"):
            preview = _preview_message(result, limit=TRUNCATE_RESULT)

        logger.info(
            f"{trace_prefix}[tool] done name={tool_name} elapsed_ms={elapsed:.1f} result_preview={preview}"
        )
        _write_trace(
            request.runtime,
            "tool_end",
            tool=tool_name,
            elapsed_ms=elapsed,
            result_preview=preview,
        )

        if tool_name == "fill_context_for_report":
            request.runtime.context["report"] = True
            logger.info(f"{trace_prefix}[tool] set report=True by fill_context_for_report")

        return result
    except Exception as exc:  # pragma: no cover
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception(f"{trace_prefix}[tool] fail name={tool_name} elapsed_ms={elapsed:.1f} error={exc}")
        _write_trace(
            request.runtime,
            "tool_error",
            tool=tool_name,
            elapsed_ms=elapsed,
            error=str(exc),
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
        logger.debug(
            "%s[model] last message type=%s len=%s preview=%s",
            trace_prefix,
            type(last).__name__,
            len(getattr(last, "content", "") or ""),
            _preview_message(last, limit=TRUNCATE_PREVIEW),
        )
    _write_trace(
        runtime,
        "model_prepare",
        messages=len(messages),
        preview=_message_snapshot(messages),
        report=runtime.context.get("report", False),
    )
    return None


@wrap_model_call
def log_model_call(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]):
    """Wrap the LLM call to time it and capture the full prompt/response outline."""
    start = time.perf_counter()
    trace_prefix = _log_prefix(request.runtime)
    model_name = getattr(request.model, "model_name", None) or getattr(request.model, "model", None) or type(request.model).__name__

    logger.info(
        f"{trace_prefix}[model] start name={model_name} messages={len(request.messages)} tools={len(request.tools or [])} report={request.runtime.context.get('report', False)}"
    )
    _write_trace(
        request.runtime,
        "model_start",
        model=model_name,
        messages=len(request.messages),
        tools=len(request.tools or []),
        prompt_snapshot=_message_snapshot(request.messages),
        report=request.runtime.context.get("report", False),
    )

    try:
        response = handler(request)
        elapsed = (time.perf_counter() - start) * 1000
        outputs = _result_messages(response)
        previews = _message_snapshot(outputs)
        first_preview = previews[0]["preview"] if previews else ""

        logger.info(
            f"{trace_prefix}[model] done name={model_name} elapsed_ms={elapsed:.1f} outputs={len(outputs)} first_preview={first_preview}"
        )
        _write_trace(
            request.runtime,
            "model_end",
            model=model_name,
            elapsed_ms=elapsed,
            outputs=len(outputs),
            output_preview=previews,
        )
        return response
    except Exception as exc:  # pragma: no cover
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception(f"{trace_prefix}[model] fail name={model_name} elapsed_ms={elapsed:.1f} error={exc}")
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
    previews = _message_snapshot(outputs)
    logger.debug(
        "%s[model] after_model outputs=%s preview=%s",
        trace_prefix,
        len(outputs),
        previews[:2],
    )
    _write_trace(
        runtime,
        "model_after",
        outputs=len(outputs),
        preview=previews,
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
