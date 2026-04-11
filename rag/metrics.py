import threading
from collections import deque
from datetime import datetime
from typing import Any

_lock = threading.Lock()
_window = deque(maxlen=200)
_summary = {
    "total_queries": 0,
    "success_queries": 0,
    "failed_queries": 0,
    "empty_reference_queries": 0,
}


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def record_rag_metric(event: dict[str, Any]) -> None:
    item = dict(event or {})
    item["ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        _summary["total_queries"] += 1
        if item.get("ok", False):
            _summary["success_queries"] += 1
        else:
            _summary["failed_queries"] += 1
        if _safe_int(item.get("reference_count", 0)) == 0:
            _summary["empty_reference_queries"] += 1
        _window.append(item)


def reset_rag_metrics() -> str:
    with _lock:
        _window.clear()
        _summary["total_queries"] = 0
        _summary["success_queries"] = 0
        _summary["failed_queries"] = 0
        _summary["empty_reference_queries"] = 0
    return "已重置 RAG 运行指标。"


def get_rag_metrics_markdown() -> str:
    with _lock:
        events = list(_window)
        summary = dict(_summary)

    if not events:
        return "### 📈 在线 RAG 指标\n> 暂无运行数据。"

    count = len(events)
    # fmt: off
    avg_total_ms = sum(_safe_int(item.get("total_ms", 0)) for item in events) / max(1, count)
    avg_retrieval_ms = sum(_safe_int(item.get("retrieval_ms", 0)) for item in events) / max(1, count)
    avg_rerank_ms = sum(_safe_int(item.get("rerank_ms", 0)) for item in events) / max(1, count)
    avg_llm_ms = sum(_safe_int(item.get("llm_ms", 0)) for item in events) / max(1, count)
    avg_candidates = sum(_safe_int(item.get("candidate_count", 0)) for item in events) / max(1, count)
    avg_references = sum(_safe_int(item.get("reference_count", 0)) for item in events) / max(1, count)
    # fmt: on

    by_strategy: dict[str, int] = {}
    for item in events:
        strategy = str(item.get("strategy", "unknown"))
        by_strategy[strategy] = by_strategy.get(strategy, 0) + 1

    recent_lines = []
    for item in events[-8:]:
        recent_lines.append(
            f"- `{item.get('ts')}` | ok={item.get('ok')} | strategy=`{item.get('strategy','unknown')}`"
            f" | refs={item.get('reference_count',0)} | total={item.get('total_ms',0)}ms"
        )

    strategy_lines = [
        f"- `{k}`: {v}"
        for k, v in sorted(by_strategy.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return "\n".join(
        [
            "### 📈 在线 RAG 指标",
            f"- 总查询：`{summary['total_queries']}`",
            f"- 成功：`{summary['success_queries']}`，失败：`{summary['failed_queries']}`",
            f"- 空命中查询：`{summary['empty_reference_queries']}`",
            f"- 平均总耗时：`{avg_total_ms:.1f} ms`（检索 `{avg_retrieval_ms:.1f}` / 重排 `{avg_rerank_ms:.1f}` / 生成 `{avg_llm_ms:.1f}`）",
            f"- 平均候选数：`{avg_candidates:.1f}`，平均最终片段数：`{avg_references:.1f}`",
            "",
            "#### 检索策略分布（当前窗口）",
            *strategy_lines,
            "",
            "#### 最近请求",
            *recent_lines,
        ]
    )
