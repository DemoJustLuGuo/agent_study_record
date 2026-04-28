import hashlib
import importlib.util
import os
from pathlib import Path
from typing import Any, Callable

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    CSVLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredWordDocumentLoader,
)

from utils.log import logger

LoaderFunc = Callable[[str, dict[str, Any]], list[Document]]

DEFAULT_LOADER_PRIORITY: dict[str, list[str]] = {
    "pdf": ["pypdf"],
    "txt": ["text"],
    "md": ["unstructured_markdown", "text"],
    "docx": ["unstructured_docx", "text"],
    "html": ["unstructured_html", "text"],
    "htm": ["unstructured_html", "text"],
    "csv": ["csv"],
}


def get_file_md5_hex(filepath: str):
    if not os.path.exists(filepath):
        logger.error(f"文件{filepath}不存在")
        return

    if not os.path.isfile(filepath):
        logger.error(f"{filepath}不是一个文件")
        return

    md5_obj = hashlib.md5()
    chunk_size = 4096
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)
            md5_hex = md5_obj.hexdigest()
            return md5_hex
    except Exception as e:
        logger.error(f"计算文件{filepath}的MD5值时发生错误: {str(e)}")
        return None


def listdir_with_allowed_type(
    path: str, allowed_types: tuple[str, ...]
) -> tuple[str, ...]:
    files = []
    if not os.path.isdir(path):
        logger.error(f"[listdir_with_allowed_type]{path}不是一个目录")
        return tuple()

    for f in os.listdir(path):
        if f.endswith(allowed_types):
            files.append(os.path.join(path, f))
    return tuple(files)


def _clean_documents(docs: list[Document]) -> list[Document]:
    cleaned = []
    for doc in docs or []:
        if not doc or not str(getattr(doc, "page_content", "")).strip():
            continue
        cleaned.append(doc)
    return cleaned


def _load_with_text(filepath: str, _: dict[str, Any]) -> list[Document]:
    return TextLoader(filepath, encoding="utf-8").load()


def _load_with_pypdf(filepath: str, loader_conf: dict[str, Any]) -> list[Document]:
    pdf_conf = loader_conf.get("pdf", {})
    extraction_mode = str(pdf_conf.get("pypdf_extraction_mode", "layout"))
    mode = str(pdf_conf.get("pypdf_mode", "page"))
    return PyPDFLoader(
        filepath,
        mode=mode,
        extraction_mode=extraction_mode,
    ).load()


def _load_with_unstructured_markdown(
    filepath: str, _: dict[str, Any]
) -> list[Document]:
    if importlib.util.find_spec("unstructured") is None:
        raise RuntimeError("未安装unstructured依赖")
    return UnstructuredMarkdownLoader(filepath, mode="elements").load()


def _load_with_unstructured_docx(filepath: str, _: dict[str, Any]) -> list[Document]:
    if importlib.util.find_spec("unstructured") is None:
        raise RuntimeError("未安装unstructured依赖")
    return UnstructuredWordDocumentLoader(filepath, mode="elements").load()


def _load_with_unstructured_html(filepath: str, _: dict[str, Any]) -> list[Document]:
    if importlib.util.find_spec("unstructured") is None:
        raise RuntimeError("未安装unstructured依赖")
    return UnstructuredHTMLLoader(filepath, mode="elements").load()


def _load_with_csv(filepath: str, _: dict[str, Any]) -> list[Document]:
    return CSVLoader(filepath, autodetect_encoding=True).load()


LOADER_FUNC_MAP: dict[str, LoaderFunc] = {
    "pypdf": _load_with_pypdf,
    "text": _load_with_text,
    "unstructured_markdown": _load_with_unstructured_markdown,
    "unstructured_docx": _load_with_unstructured_docx,
    "unstructured_html": _load_with_unstructured_html,
    "csv": _load_with_csv,
}


def _resolve_loader_priority(
    ext_without_dot: str, loader_conf: dict[str, Any]
) -> list[str]:
    configured = loader_conf.get("loader_priority", {})
    if isinstance(configured, dict):
        configured_priority = configured.get(ext_without_dot, None)
        if isinstance(configured_priority, list) and configured_priority:
            return [
                str(item).strip() for item in configured_priority if str(item).strip()
            ]

    return DEFAULT_LOADER_PRIORITY.get(ext_without_dot, ["text"])


def load_documents_by_path(
    filepath: str,
    loader_conf: dict[str, Any] | None = None,
) -> tuple[list[Document], str]:
    config = loader_conf or {}
    ext_without_dot = Path(filepath).suffix.lower().lstrip(".")
    loader_priority = _resolve_loader_priority(ext_without_dot, config)

    errors: list[str] = []
    for loader_name in loader_priority:
        loader = LOADER_FUNC_MAP.get(loader_name)
        if loader is None:
            errors.append(f"{loader_name}: 未注册加载策略")
            continue
        try:
            docs = _clean_documents(loader(filepath, config))
            if docs:
                return docs, loader_name
            errors.append(f"{loader_name}: 返回空文档")
        except Exception as e:
            errors.append(f"{loader_name}: {e}")

    logger.warning(
        "文件%s加载失败，尝试策略=%s，错误=%s",
        filepath,
        loader_priority,
        " | ".join(errors),
    )
    return [], ""
