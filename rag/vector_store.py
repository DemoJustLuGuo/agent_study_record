import argparse
import hashlib
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from model.factory import embeddings_model
from utils.config_handler import chroma_conf
from utils.file_handler import get_file_md5_hex, load_documents_by_path
from utils.log import logger
from utils.path_tools import get_abs_path


class _HTMLTextExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "p",
        "div",
        "br",
        "li",
        "tr",
        "td",
        "th",
        "section",
        "article",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "pre",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = (data or "").strip()
        if text:
            self._parts.append(text)

    def get_text(self) -> str:
        raw = " ".join(self._parts)
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        return "\n".join(line for line in lines if line).strip()


class VectorStoreService:
    _auto_sync_lock = threading.Lock()
    _last_auto_sync_ts = 0.0

    def __init__(self, enable_auto_sync: bool = True):
        self.persist_directory = get_abs_path(chroma_conf["persist_directory"])
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embeddings_model,
            persist_directory=self.persist_directory,
        )
        self.enable_auto_sync = enable_auto_sync
        self.auto_sync_on_init = bool(chroma_conf.get("auto_sync_on_init", True))
        self.auto_sync_before_retrieval = bool(
            chroma_conf.get("auto_sync_before_retrieval", True)
        )
        self.auto_sync_min_interval_seconds = int(
            chroma_conf.get("auto_sync_min_interval_seconds", 30)
        )
        self.document_loader_conf = chroma_conf.get("document_loader", {})
        self.chunking_conf = chroma_conf.get("chunking", {})
        self._splitter_cache: dict[str, RecursiveCharacterTextSplitter] = {}
        self._keyword_corpus_cache: tuple[float, list[Document]] = (0.0, [])

        if self.enable_auto_sync and self.auto_sync_on_init:
            self.auto_sync_data_dir(trigger="init")

    def _md5_store_path(self) -> str:
        return get_abs_path(chroma_conf["md5_hex_store"])

    def _manifest_store_path(self) -> str:
        return get_abs_path(chroma_conf.get("index_manifest_store", "chroma_manifest.json"))

    def _snapshot_root_path(self) -> str:
        return get_abs_path(chroma_conf.get("lifecycle_snapshot_dir", "chroma_snapshots"))

    def _ensure_parent_dir(self, file_path: str):
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    def _load_md5_store(self) -> set[str]:
        md5_store_path = self._md5_store_path()
        if not os.path.exists(md5_store_path):
            self._write_md5_store(set())
            return set()

        with open(md5_store_path, "r", encoding="utf-8") as file_obj:
            return {line.strip() for line in file_obj.readlines() if line.strip()}

    def _write_md5_store(self, md5_values: set[str]):
        md5_store_path = self._md5_store_path()
        self._ensure_parent_dir(md5_store_path)
        with open(md5_store_path, "w", encoding="utf-8") as file_obj:
            for md5_hex in sorted(md5_values):
                file_obj.write(md5_hex + "\n")

    def _load_manifest(self) -> dict[str, dict]:
        manifest_store_path = self._manifest_store_path()
        if not os.path.exists(manifest_store_path):
            self._save_manifest({})
            return {}

        try:
            with open(manifest_store_path, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
                if isinstance(data, dict):
                    return data
        except Exception as error:
            logger.warning(f"索引清单读取失败，已回退为空清单: {str(error)}")
        return {}

    def _save_manifest(self, manifest: dict[str, dict]):
        manifest_store_path = self._manifest_store_path()
        self._ensure_parent_dir(manifest_store_path)
        with open(manifest_store_path, "w", encoding="utf-8") as file_obj:
            json.dump(manifest, file_obj, ensure_ascii=False, indent=2)

    def _manifest_entry(self, md5_hex: str, source_type: str, operator: str) -> dict[str, str]:
        return {
            "md5": md5_hex,
            "source_type": source_type,
            "operator": operator,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _sync_md5_store_with_manifest(self, manifest: dict[str, dict]):
        md5_values = {
            item.get("md5", "")
            for item in manifest.values()
            if item.get("md5", "")
        }
        self._write_md5_store(md5_values)

    def _delete_vectors_by_source(self, source: str):
        try:
            self.vector_store.delete(where={"source": source})
            logger.info(f"已删除source={source}对应向量数据")
        except Exception as error:
            logger.error(f"删除source={source}对应向量数据失败: {str(error)}", exc_info=True)

    def _drop_removed_file_sources(self, manifest: dict[str, dict]) -> list[str]:
        removed_sources: list[str] = []
        for source, entry in list(manifest.items()):
            if entry.get("source_type") != "file_scan":
                continue
            if os.path.exists(source):
                continue

            self._delete_vectors_by_source(source)
            manifest.pop(source, None)
            removed_sources.append(source)
            logger.info(f"源文件已删除，已从索引清单移除: {source}")

        return removed_sources

    def _normalize_source_path(self, source_path: str) -> str:
        return os.path.normpath(os.path.abspath(source_path))

    def sync_removed_sources(self) -> dict[str, object]:
        manifest = self._load_manifest()
        removed_sources = self._drop_removed_file_sources(manifest)
        self._save_manifest(manifest)
        self._sync_md5_store_with_manifest(manifest)
        return {
            "removed_source_count": len(removed_sources),
            "removed_sources": removed_sources,
        }

    def create_snapshot(self, tag: str = "") -> str:
        snapshot_root = self._snapshot_root_path()
        os.makedirs(snapshot_root, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_tag = "".join(c for c in tag.strip() if c.isalnum() or c in ("-", "_"))
        snapshot_name = f"{timestamp}_{safe_tag}" if safe_tag else timestamp
        snapshot_path = os.path.join(snapshot_root, snapshot_name)
        os.makedirs(snapshot_path, exist_ok=False)

        snapshot_vector_path = os.path.join(snapshot_path, "vector_store")
        if os.path.exists(self.persist_directory):
            shutil.copytree(self.persist_directory, snapshot_vector_path)
        else:
            os.makedirs(snapshot_vector_path, exist_ok=True)

        md5_store_path = self._md5_store_path()
        snapshot_md5_path = os.path.join(snapshot_path, os.path.basename(md5_store_path))
        if os.path.exists(md5_store_path):
            shutil.copy2(md5_store_path, snapshot_md5_path)
        else:
            open(snapshot_md5_path, "w", encoding="utf-8").close()

        manifest_store_path = self._manifest_store_path()
        snapshot_manifest_path = os.path.join(
            snapshot_path, os.path.basename(manifest_store_path)
        )
        if os.path.exists(manifest_store_path):
            shutil.copy2(manifest_store_path, snapshot_manifest_path)
        else:
            with open(snapshot_manifest_path, "w", encoding="utf-8") as file_obj:
                json.dump({}, file_obj, ensure_ascii=False, indent=2)

        logger.info(f"向量生命周期快照创建成功: {snapshot_name}")
        return snapshot_name

    def rollback_snapshot(self, snapshot_name: str) -> str:
        snapshot_path = os.path.join(self._snapshot_root_path(), snapshot_name)
        if not os.path.isdir(snapshot_path):
            raise FileNotFoundError(f"快照不存在: {snapshot_name}")

        snapshot_vector_path = os.path.join(snapshot_path, "vector_store")
        if not os.path.isdir(snapshot_vector_path):
            raise FileNotFoundError(f"快照向量目录不存在: {snapshot_vector_path}")

        if os.path.exists(self.persist_directory):
            shutil.rmtree(self.persist_directory)
        shutil.copytree(snapshot_vector_path, self.persist_directory)

        md5_store_path = self._md5_store_path()
        manifest_store_path = self._manifest_store_path()
        snapshot_md5_path = os.path.join(snapshot_path, os.path.basename(md5_store_path))
        snapshot_manifest_path = os.path.join(
            snapshot_path, os.path.basename(manifest_store_path)
        )

        self._ensure_parent_dir(md5_store_path)
        self._ensure_parent_dir(manifest_store_path)

        if os.path.exists(snapshot_md5_path):
            shutil.copy2(snapshot_md5_path, md5_store_path)
        else:
            open(md5_store_path, "w", encoding="utf-8").close()

        if os.path.exists(snapshot_manifest_path):
            shutil.copy2(snapshot_manifest_path, manifest_store_path)
        else:
            with open(manifest_store_path, "w", encoding="utf-8") as file_obj:
                json.dump({}, file_obj, ensure_ascii=False, indent=2)

        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embeddings_model,
            persist_directory=self.persist_directory,
        )

        logger.info(f"已回滚到向量生命周期快照: {snapshot_name}")
        return snapshot_name

    def _check_md5_hex(self, md5_for_check: str) -> bool:
        return md5_for_check in self._load_md5_store()

    def _resolve_chunk_conf(self, source_type: str, source_path: str = "") -> dict[str, object]:
        default_conf = self.chunking_conf.get("default", {})
        source_conf_map = self.chunking_conf.get("source_type", {})
        file_conf_map = self.chunking_conf.get("file_type", {})
        ext = os.path.splitext(source_path)[1].lower().lstrip(".")

        conf = {
            "chunk_size": int(default_conf.get("chunk_size", chroma_conf.get("chunk_size", 200))),
            "chunk_overlap": int(
                default_conf.get("chunk_overlap", chroma_conf.get("chunk_overlap", 20))
            ),
            "separators": default_conf.get("separators", chroma_conf.get("separator", ["\n\n", "\n"])),
        }
        if source_type in source_conf_map:
            conf.update(source_conf_map[source_type] or {})
        if ext and ext in file_conf_map:
            conf.update(file_conf_map[ext] or {})
        conf["chunk_size"] = int(conf["chunk_size"])
        conf["chunk_overlap"] = int(conf["chunk_overlap"])
        conf["separators"] = list(conf.get("separators", chroma_conf.get("separator", ["\n\n", "\n"])))
        return conf

    def _get_splitter(self, source_type: str, source_path: str = "") -> RecursiveCharacterTextSplitter:
        conf = self._resolve_chunk_conf(source_type=source_type, source_path=source_path)
        cache_key = f"{source_type}|{os.path.splitext(source_path)[1].lower()}|{conf['chunk_size']}|{conf['chunk_overlap']}|{hash(tuple(conf['separators']))}"
        splitter = self._splitter_cache.get(cache_key)
        if splitter is not None:
            return splitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=conf["chunk_size"],
            chunk_overlap=conf["chunk_overlap"],
            separators=conf["separators"],
            length_function=len,
        )
        self._splitter_cache[cache_key] = splitter
        return splitter

    @staticmethod
    def _attach_chunk_metadata(
        docs: list[Document],
        source: str,
        source_type: str,
        source_md5: str,
        indexed_time: str,
        extra_metadata: dict[str, object] | None = None,
    ) -> list[Document]:
        total = len(docs)
        extra = extra_metadata or {}
        for idx, doc in enumerate(docs, start=1):
            if doc.metadata is None:
                doc.metadata = {}
            doc.metadata["source"] = source
            doc.metadata["source_md5"] = source_md5
            doc.metadata["source_type"] = source_type
            doc.metadata["indexed_at"] = indexed_time
            doc.metadata["chunk_index"] = idx
            doc.metadata["chunk_count"] = total
            for key, value in extra.items():
                doc.metadata[key] = value
        return docs

    @staticmethod
    def _normalize_web_url(url: str) -> str:
        text = (url or "").strip()
        if not text:
            return ""
        parsed = urlparse(text)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return ""
        return parsed.geturl()

    @staticmethod
    def _fetch_web_text(
        url: str,
        timeout_seconds: float,
        user_agent: str,
        max_content_chars: int,
    ) -> str:
        request = Request(url, headers={"User-Agent": user_agent})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read(max(max_content_chars * 2, 4096))
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(charset, errors="replace")
                content_type = str(response.headers.get("Content-Type", "")).lower()
        except URLError as error:
            raise RuntimeError(f"网络请求失败: {error}") from error

        if "html" in content_type or "<html" in text.lower():
            parser = _HTMLTextExtractor()
            parser.feed(text)
            parsed_text = parser.get_text()
        else:
            parsed_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())

        if len(parsed_text) > max_content_chars:
            return parsed_text[:max_content_chars]
        return parsed_text

    @staticmethod
    def _tokenize_for_keyword(text: str) -> list[str]:
        tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", (text or "").lower())
        return [token for token in tokens if token.strip()]

    @staticmethod
    def _doc_key(doc: Document) -> str:
        metadata = doc.metadata or {}
        source = str(metadata.get("source", ""))
        chunk_idx = str(metadata.get("chunk_index", ""))
        content = str(doc.page_content or "")
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:16]
        return f"{source}|{chunk_idx}|{content_hash}"

    def _load_keyword_corpus(self) -> list[Document]:
        retrieval_conf = chroma_conf.get("retrieval", {})
        keyword_conf = retrieval_conf.get("keyword", {})
        cache_ttl_seconds = int(keyword_conf.get("cache_ttl_seconds", 60))
        now = time.time()
        cache_ts, cache_docs = self._keyword_corpus_cache
        if cache_docs and cache_ttl_seconds > 0 and now - cache_ts < cache_ttl_seconds:
            return cache_docs

        raw = self.vector_store.get(include=["documents", "metadatas"])
        documents = raw.get("documents") or []
        metadatas = raw.get("metadatas") or []
        docs: list[Document] = []
        for idx, content in enumerate(documents):
            text = str(content or "").strip()
            if not text:
                continue
            metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
            docs.append(Document(page_content=text, metadata=metadata))
        self._keyword_corpus_cache = (now, docs)
        return docs

    def _keyword_retrieve(self, query: str, top_k: int) -> list[Document]:
        if top_k <= 0:
            return []
        query_tokens = self._tokenize_for_keyword(query)
        if not query_tokens:
            return []

        query_set = set(query_tokens)
        scored: list[tuple[float, Document]] = []
        for doc in self._load_keyword_corpus():
            content = doc.page_content or ""
            doc_tokens = self._tokenize_for_keyword(content)
            if not doc_tokens:
                continue
            overlap = sum(1 for token in doc_tokens if token in query_set)
            if overlap == 0:
                continue
            unique_overlap = len(set(doc_tokens) & query_set)
            phrase_bonus = 0.3 if query.strip() and query.strip().lower() in content.lower() else 0.0
            density = overlap / max(1, len(doc_tokens))
            score = unique_overlap + density + phrase_bonus
            scored.append((score, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def hybrid_retrieve(self, query: str) -> tuple[list[Document], dict[str, object]]:
        retrieval_conf = chroma_conf.get("retrieval", {})
        hybrid_enabled = bool(retrieval_conf.get("hybrid_enabled", True))
        keyword_enabled = bool(retrieval_conf.get("keyword_enabled", True))
        vector_k = int(retrieval_conf.get("vector_k", max(8, int(chroma_conf.get("k", 3)))))
        keyword_k = int(retrieval_conf.get("keyword_k", max(8, int(chroma_conf.get("k", 3)))))
        candidate_k = int(retrieval_conf.get("candidate_k", max(vector_k, keyword_k, int(chroma_conf.get("k", 3)))))
        rrf_k = int(retrieval_conf.get("rrf_k", 60))
        final_k = int(retrieval_conf.get("final_k", int(chroma_conf.get("k", 3))))

        start_time = time.perf_counter()
        vector_start = time.perf_counter()
        vector_docs = self.vector_store.similarity_search(query, k=max(vector_k, final_k))
        vector_elapsed_ms = int((time.perf_counter() - vector_start) * 1000)

        if not hybrid_enabled:
            docs = vector_docs[:candidate_k]
            return docs, {
                "strategy": "vector_only",
                "vector_hits": len(vector_docs),
                "keyword_hits": 0,
                "candidate_count": len(docs),
                "final_k": final_k,
                "elapsed_ms": int((time.perf_counter() - start_time) * 1000),
                "vector_elapsed_ms": vector_elapsed_ms,
                "keyword_elapsed_ms": 0,
            }

        keyword_elapsed_ms = 0
        keyword_docs: list[Document] = []
        if keyword_enabled:
            keyword_start = time.perf_counter()
            keyword_docs = self._keyword_retrieve(query=query, top_k=max(keyword_k, final_k))
            keyword_elapsed_ms = int((time.perf_counter() - keyword_start) * 1000)

        fused_scores: dict[str, float] = {}
        doc_by_key: dict[str, Document] = {}

        for rank, doc in enumerate(vector_docs, start=1):
            key = self._doc_key(doc)
            doc_by_key[key] = doc
            fused_scores[key] = fused_scores.get(key, 0.0) + 1.0 / (rrf_k + rank)

        for rank, doc in enumerate(keyword_docs, start=1):
            key = self._doc_key(doc)
            doc_by_key[key] = doc
            fused_scores[key] = fused_scores.get(key, 0.0) + 1.0 / (rrf_k + rank)

        ranked = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
        candidates = [doc_by_key[key] for key, _ in ranked[:candidate_k]]
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return candidates, {
            "strategy": "hybrid_rrf",
            "vector_hits": len(vector_docs),
            "keyword_hits": len(keyword_docs),
            "candidate_count": len(candidates),
            "final_k": final_k,
            "rrf_k": rrf_k,
            "elapsed_ms": elapsed_ms,
            "vector_elapsed_ms": vector_elapsed_ms,
            "keyword_elapsed_ms": keyword_elapsed_ms,
        }

    def get_retriever(self):
        if self.enable_auto_sync and self.auto_sync_before_retrieval:
            self.auto_sync_data_dir(trigger="get_retriever")
        retrieval_conf = chroma_conf.get("retrieval", {})
        top_k = int(retrieval_conf.get("final_k", chroma_conf.get("k", 3)))
        return self.vector_store.as_retriever(search_kwargs={"k": top_k})

    @staticmethod
    def _normalize_allowed_extensions(
        allowed_types: list[str] | tuple[str, ...]
    ) -> tuple[str, ...]:
        normalized = []
        for item in allowed_types:
            ext = str(item).strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            normalized.append(ext)
        return tuple(normalized)

    def _list_knowledge_files(self) -> tuple[str, ...]:
        data_root = get_abs_path(chroma_conf["data_path"])
        allowed_extensions = self._normalize_allowed_extensions(
            chroma_conf["allowed_knowledge_file_type"]
        )
        if not os.path.isdir(data_root):
            logger.error(f"[load_documents]{data_root}不是一个目录")
            return tuple()

        files: list[str] = []
        for root, _, filenames in os.walk(data_root):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                if full_path.lower().endswith(allowed_extensions):
                    files.append(full_path)
        files.sort()
        return tuple(files)

    def auto_sync_data_dir(self, trigger: str = "runtime") -> dict[str, object]:
        if not self.enable_auto_sync:
            return {"status": "disabled", "trigger": trigger}

        now = time.time()
        if (
            self.auto_sync_min_interval_seconds > 0
            and now - self.__class__._last_auto_sync_ts < self.auto_sync_min_interval_seconds
        ):
            return {"status": "skipped", "trigger": trigger, "reason": "interval_limit"}

        with self.__class__._auto_sync_lock:
            now = time.time()
            if (
                self.auto_sync_min_interval_seconds > 0
                and now - self.__class__._last_auto_sync_ts < self.auto_sync_min_interval_seconds
            ):
                return {"status": "skipped", "trigger": trigger, "reason": "interval_limit"}

            result = self.load_documents()
            self.__class__._last_auto_sync_ts = time.time()
            result["status"] = "synced"
            result["trigger"] = trigger
            return result

    def upload_text(self, data: str, filename: str, operator: str = "admin") -> str:
        text = (data or "").strip()
        if not text:
            return "【失败】文本内容为空"

        md5_hex = hashlib.md5(text.encode("utf-8")).hexdigest()
        if self._check_md5_hex(md5_hex):
            logger.info("文本内容已存在于知识库中，跳过入库")
            return "【跳过】内容已经存在于知识库中"

        splitter = self._get_splitter(source_type="text_upload")
        knowledge_chunks = splitter.split_text(text) if len(text) > 0 else []
        knowledge_chunks = [chunk for chunk in knowledge_chunks if str(chunk).strip()]
        if not knowledge_chunks:
            logger.warning("文本切分后为空，未执行入库")
            return "【失败】文本切分后为空"

        self._delete_vectors_by_source(filename)
        indexed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        chunk_count = len(knowledge_chunks)
        metadatas = []
        for idx, _ in enumerate(knowledge_chunks, start=1):
            metadatas.append(
                {
                    "source": filename,
                    "create_time": indexed_time,
                    "indexed_at": indexed_time,
                    "operator": operator,
                    "source_md5": md5_hex,
                    "source_type": "text_upload",
                    "chunk_index": idx,
                    "chunk_count": chunk_count,
                }
            )
        self.vector_store.add_texts(knowledge_chunks, metadatas=metadatas)

        manifest = self._load_manifest()
        manifest[filename] = self._manifest_entry(
            md5_hex=md5_hex,
            source_type="text_upload",
            operator=operator,
        )
        self._save_manifest(manifest)
        self._sync_md5_store_with_manifest(manifest)
        logger.info(f"文本{filename}已成功上传到向量数据库 chunks={chunk_count}")
        return "【成功】内容已成功添加到知识库中"

    def upsert_web_urls(self, urls: list[str], operator: str = "admin") -> dict[str, object]:
        web_conf = chroma_conf.get("web_source", {})
        timeout_seconds = float(web_conf.get("timeout_seconds", 20))
        min_content_chars = int(web_conf.get("min_content_chars", 80))
        max_content_chars = int(web_conf.get("max_content_chars", 50000))
        user_agent = str(
            web_conf.get(
                "user_agent",
                "Mozilla/5.0 (compatible; AgentStudyRAG/1.0; +https://example.local)",
            )
        )

        manifest = self._load_manifest()
        added = 0
        updated = 0
        skipped = 0
        failed = 0
        details: list[dict[str, str]] = []
        logger.info(
            "网页入库开始: total=%s operator=%s timeout=%s min_chars=%s",
            len(urls),
            operator,
            timeout_seconds,
            min_content_chars,
        )

        for raw_url in urls:
            url = self._normalize_web_url(raw_url)
            if not url:
                failed += 1
                details.append({"url": raw_url, "status": "failed", "reason": "invalid_url"})
                logger.warning("网页入库失败: invalid_url raw=%s", raw_url)
                continue

            source = f"url::{url}"
            try:
                content = self._fetch_web_text(
                    url=url,
                    timeout_seconds=timeout_seconds,
                    user_agent=user_agent,
                    max_content_chars=max_content_chars,
                )
            except Exception as error:
                failed += 1
                details.append({"url": url, "status": "failed", "reason": str(error)})
                logger.warning("网页入库失败: url=%s reason=%s", url, error)
                continue

            if len(content) < min_content_chars:
                failed += 1
                details.append(
                    {"url": url, "status": "failed", "reason": f"content_too_short:{len(content)}"}
                )
                logger.warning("网页入库失败: url=%s content_too_short=%s", url, len(content))
                continue

            md5_hex = hashlib.md5(content.encode("utf-8")).hexdigest()
            old_entry = manifest.get(source, {})
            old_md5 = str(old_entry.get("md5", ""))

            if old_md5 == md5_hex and self._check_md5_hex(md5_hex):
                skipped += 1
                details.append({"url": url, "status": "skipped", "reason": "unchanged"})
                logger.debug("网页入库跳过: url=%s reason=unchanged", url)
                continue

            if old_md5 and old_md5 != md5_hex:
                self._delete_vectors_by_source(source)
                is_update = True
            else:
                is_update = bool(old_entry)

            if not old_entry and self._check_md5_hex(md5_hex):
                manifest[source] = self._manifest_entry(
                    md5_hex=md5_hex,
                    source_type="web_url",
                    operator=operator,
                )
                skipped += 1
                details.append({"url": url, "status": "skipped", "reason": "duplicate_content"})
                logger.debug("网页入库跳过: url=%s reason=duplicate_content", url)
                continue

            splitter = self._get_splitter(source_type="web_url")
            chunks = splitter.split_text(content)
            chunks = [chunk for chunk in chunks if str(chunk).strip()]
            if not chunks:
                failed += 1
                details.append({"url": url, "status": "failed", "reason": "empty_chunks"})
                logger.warning("网页入库失败: url=%s reason=empty_chunks", url)
                continue

            indexed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            chunk_count = len(chunks)
            metadatas = []
            for idx, _ in enumerate(chunks, start=1):
                metadatas.append(
                    {
                        "source": source,
                        "url": url,
                        "source_md5": md5_hex,
                        "source_type": "web_url",
                        "indexed_at": indexed_time,
                        "operator": operator,
                        "chunk_index": idx,
                        "chunk_count": chunk_count,
                    }
                )
            self.vector_store.add_texts(chunks, metadatas=metadatas)

            manifest[source] = self._manifest_entry(
                md5_hex=md5_hex,
                source_type="web_url",
                operator=operator,
            )

            if is_update:
                updated += 1
                details.append({"url": url, "status": "updated"})
                logger.info("网页入库更新: url=%s chunks=%s", url, len(chunks))
            else:
                added += 1
                details.append({"url": url, "status": "added"})
                logger.info("网页入库新增: url=%s chunks=%s", url, len(chunks))

        self._save_manifest(manifest)
        self._sync_md5_store_with_manifest(manifest)
        logger.info(
            "网页入库完成: 新增=%s, 更新=%s, 跳过=%s, 失败=%s",
            added,
            updated,
            skipped,
            failed,
        )
        return {
            "added": added,
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "total": len(urls),
            "details": details,
        }

    def load_documents(self):
        manifest = self._load_manifest()
        allowed_files_path = self._list_knowledge_files()

        add_count = 0
        update_count = 0
        total_chunks = 0

        for path in allowed_files_path:
            source_path = self._normalize_source_path(path)
            md5_hex = get_file_md5_hex(path)
            if not md5_hex:
                logger.warning(f"文件{path}的MD5计算失败，跳过")
                continue

            old_entry = manifest.get(source_path, {})
            old_md5 = old_entry.get("md5", "")
            if old_md5 == md5_hex and self._check_md5_hex(md5_hex):
                logger.info(f"文件{path}已处理过，跳过")
                continue

            if not old_entry and self._check_md5_hex(md5_hex):
                manifest[source_path] = self._manifest_entry(
                    md5_hex=md5_hex,
                    source_type="file_scan",
                    operator="system",
                )
                logger.info(f"文件{path}已存在于MD5记录，已补齐source映射")
                continue

            if old_md5 and old_md5 != md5_hex:
                self._delete_vectors_by_source(source_path)
                update_count += 1

            try:
                documents, loader_name = load_documents_by_path(
                    path,
                    loader_conf=self.document_loader_conf,
                )
                if not documents:
                    logger.warning(f"文件{path}没有加载到任何文档，可能是格式不受支持")
                    continue

                splitter = self._get_splitter(source_type="file_scan", source_path=path)
                split_documents: list[Document] = splitter.split_documents(documents)
                if not split_documents:
                    logger.warning(f"文件{path}没有被分割成任何文档，可能是切分配置不合理")
                    continue

                indexed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                split_documents = self._attach_chunk_metadata(
                    docs=split_documents,
                    source=source_path,
                    source_type="file_scan",
                    source_md5=md5_hex,
                    indexed_time=indexed_time,
                    extra_metadata={"parse_loader": loader_name},
                )
                self.vector_store.add_documents(split_documents)
                total_chunks += len(split_documents)
                manifest[source_path] = self._manifest_entry(
                    md5_hex=md5_hex,
                    source_type="file_scan",
                    operator="system",
                )
                add_count += 1
                logger.info(
                    "文件%s已成功加载到向量数据库，loader=%s chunks=%s",
                    path,
                    loader_name,
                    len(split_documents),
                )
            except Exception as error:
                logger.error(f"加载文件{path}时发生错误: {str(error)}", exc_info=True)
                continue

        removed_sources = self._drop_removed_file_sources(manifest)
        self._save_manifest(manifest)
        self._sync_md5_store_with_manifest(manifest)
        self._keyword_corpus_cache = (0.0, [])

        logger.info(
            "向量库同步完成: 新增/重建=%s, 更新=%s, 删除失效源=%s, chunks=%s",
            add_count,
            update_count,
            len(removed_sources),
            total_chunks,
        )
        return {
            "added_or_rebuilt": add_count,
            "updated": update_count,
            "removed_source_count": len(removed_sources),
            "removed_sources": removed_sources,
            "scanned_file_count": len(allowed_files_path),
            "chunk_count": total_chunks,
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="向量库生命周期管理工具")
    sub_parser = parser.add_subparsers(dest="command")

    sub_parser.add_parser("load", help="扫描data目录并增量同步向量库")
    sub_parser.add_parser("sync", help="仅执行删除源文件同步清理")

    snapshot_parser = sub_parser.add_parser("snapshot", help="创建向量库快照")
    snapshot_parser.add_argument("--tag", default="", help="快照标签，可选")

    rollback_parser = sub_parser.add_parser("rollback", help="回滚到指定快照")
    rollback_parser.add_argument("snapshot", help="快照目录名")
    return parser


if __name__ == "__main__":
    parser = _build_parser()
    args = parser.parse_args()
    vector_store_service = VectorStoreService()

    if args.command in (None, "load"):
        vector_store_service.load_documents()
    elif args.command == "sync":
        sync_result = vector_store_service.sync_removed_sources()
        print(json.dumps(sync_result, ensure_ascii=False, indent=2))
    elif args.command == "snapshot":
        snapshot_name = vector_store_service.create_snapshot(args.tag)
        print(f"snapshot created: {snapshot_name}")
    elif args.command == "rollback":
        snapshot_name = vector_store_service.rollback_snapshot(args.snapshot)
        print(f"snapshot restored: {snapshot_name}")
