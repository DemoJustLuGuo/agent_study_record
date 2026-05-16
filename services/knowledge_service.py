from __future__ import annotations

from pathlib import Path
from typing import Any

from rag.knowledge_base import KnowledgeBaseService
from utils.config_handler import chroma_conf
from utils.log import logger


def parse_web_urls(urls_text: str) -> list[str]:
    raw = (urls_text or "").replace(",", "\n")
    urls = [line.strip() for line in raw.splitlines() if line.strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


class KnowledgeService:
    def __init__(self, knowledge_base: KnowledgeBaseService | None = None) -> None:
        self.knowledge_base = knowledge_base or KnowledgeBaseService()

    @staticmethod
    def allowed_upload_extensions() -> tuple[str, ...]:
        configured = chroma_conf.get("allowed_knowledge_file_type", ["txt"])
        normalized: list[str] = []
        for item in configured:
            ext = str(item).strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            normalized.append(ext)
        return tuple(normalized)

    def upload_file(self, file_path: str, operator: str = "api") -> str:
        if not file_path:
            return "请先上传知识文件。"

        source = Path(file_path)
        if source.suffix.lower() not in self.allowed_upload_extensions():
            return "不支持的文件类型。"

        # Keep current text-upload behavior while the full file ingest pipeline is split.
        if source.suffix.lower() != ".txt":
            return "当前上传入口已识别该类型，但完整多格式入库将在下一步接入。"

        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "文件编码错误：请使用 UTF-8 编码。"
        except Exception:
            logger.exception("[knowledge] upload read failed path=%s", source)
            return "系统错误：读取上传文件失败。"

        if not text.strip():
            return "文件内容为空。"

        user = (operator or "api").strip() or "api"
        try:
            result = self.knowledge_base.upload_by_str(text, source.name, operator=user)
        except Exception:
            logger.exception("[knowledge] upload write failed path=%s", source)
            return "系统错误：知识写入失败。"

        return f"✅ {result}"

    def ingest_web_urls(self, urls_text: str, operator: str = "api") -> dict[str, Any]:
        urls = parse_web_urls(urls_text)
        if not urls:
            return {"error": "请先输入至少一个 HTTP/HTTPS 链接。"}

        user = (operator or "api").strip() or "api"
        try:
            logger.info("[rag] web ingest start urls=%s operator=%s", len(urls), user)
            result = self.knowledge_base.upsert_web_urls(urls=urls, operator=user)
            logger.info(
                "[rag] web ingest done total=%s added=%s updated=%s skipped=%s failed=%s",
                result.get("total", 0),
                result.get("added", 0),
                result.get("updated", 0),
                result.get("skipped", 0),
                result.get("failed", 0),
            )
        except Exception:
            logger.exception("[rag] web ingest failed")
            return {"error": "⚠️ 系统错误：网页抓取/入库失败。"}
        return result

    def sync_removed_sources(self) -> dict[str, object]:
        try:
            return self.knowledge_base.sync_removed_sources()
        except Exception:
            logger.exception("[knowledge] sync failed")
            return {"error": "系统错误：同步失败。"}

    def create_snapshot(self, tag: str = "") -> dict[str, object]:
        try:
            name = self.knowledge_base.create_snapshot(tag=(tag or "").strip())
        except Exception:
            logger.exception("[knowledge] snapshot failed")
            return {"error": "系统错误：快照创建失败。"}
        return {"snapshot": name}

    def rollback_snapshot(
        self, snapshot_name: str, confirm_name: str = ""
    ) -> dict[str, object]:
        name = (snapshot_name or "").strip()
        if not name:
            return {"error": "请填写快照名称。"}
        try:
            restored = self.knowledge_base.rollback_snapshot(
                name,
                confirm_name=(confirm_name or "").strip(),
            )
        except FileNotFoundError:
            return {"error": "快照不存在。"}
        except ValueError as error:
            return {"error": str(error)}
        except Exception:
            logger.exception("[knowledge] rollback failed")
            return {"error": "系统错误：回滚失败。"}
        return {"snapshot": restored, "result": "ok"}
