from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.log import LOG_ROOT

TRACE_DIR = Path(LOG_ROOT) / "traces"


def _preview_text(value: object, limit: int = 800) -> str:
    text = str(value or "").replace("\n", " ")
    if len(text) > limit:
        return text[:limit] + f"...(truncated,len={len(text)})"
    return text


def _sanitize_record(record: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in record.items():
        if key == "code":
            sanitized["code_preview"] = (
                f"<redacted code,len={len(str(value or ''))}>" if value else ""
            )
            continue
        if key == "args":
            sanitized["args_preview"] = _preview_text(value)
            continue
        if key == "result":
            sanitized["result_preview"] = _preview_text(value, limit=1200)
            continue
        if key in ("input_messages", "output_messages"):
            sanitized[f"{key}_preview"] = _preview_text(value, limit=1200)
            continue
        sanitized[key] = value
    return sanitized


class TraceService:
    def __init__(self, trace_dir: Path | None = None) -> None:
        self.trace_dir = trace_dir or TRACE_DIR

    def list_traces(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.trace_dir.is_dir():
            return []
        items: list[dict[str, Any]] = []
        for path in self.trace_dir.glob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            items.append(
                {
                    "trace_id": path.stem,
                    "updated_at": stat.st_mtime,
                    "size": stat.st_size,
                }
            )
        items.sort(key=lambda item: float(item["updated_at"]), reverse=True)
        return items[: max(1, int(limit or 50))]

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        safe_id = "".join(ch for ch in (trace_id or "") if ch.isalnum() or ch in "-_")
        if not safe_id:
            raise FileNotFoundError("trace not found")
        path = (self.trace_dir / f"{safe_id}.jsonl").resolve()
        base = self.trace_dir.resolve()
        try:
            path.relative_to(base)
        except ValueError as error:
            raise FileNotFoundError("trace not found") from error
        if not path.is_file():
            raise FileNotFoundError("trace not found")

        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as file_obj:
            for line in file_obj:
                text = line.strip()
                if not text:
                    continue
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw, dict):
                    records.append(_sanitize_record(raw))
        return {"trace_id": safe_id, "events": records}
