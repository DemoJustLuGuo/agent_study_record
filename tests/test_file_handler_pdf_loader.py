from pathlib import Path

import yaml
from langchain_core.documents import Document

import utils.file_handler as file_handler


def test_pdf_default_loader_priority_only_uses_pypdf() -> None:
    assert file_handler.DEFAULT_LOADER_PRIORITY["pdf"] == ["pypdf"]
    assert "marker" not in file_handler.LOADER_FUNC_MAP
    assert "unstructured_pdf" not in file_handler.LOADER_FUNC_MAP


def test_pdf_loader_config_only_uses_pypdf() -> None:
    config_path = Path("rag/config/chroma.yml")
    chroma_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    document_loader = chroma_config["document_loader"]

    assert document_loader["loader_priority"]["pdf"] == ["pypdf"]
    assert document_loader["pdf"] == {
        "pypdf_mode": "page",
        "pypdf_extraction_mode": "layout",
    }


def test_pdf_loading_dispatches_to_pypdf_only(monkeypatch) -> None:
    calls: list[str] = []

    def fake_pypdf_loader(filepath: str, loader_conf: dict) -> list[Document]:
        calls.append(filepath)
        return [Document(page_content="pdf content")]

    monkeypatch.setitem(file_handler.LOADER_FUNC_MAP, "pypdf", fake_pypdf_loader)

    docs, loader_name = file_handler.load_documents_by_path("example.pdf")

    assert loader_name == "pypdf"
    assert calls == ["example.pdf"]
    assert [doc.page_content for doc in docs] == ["pdf content"]
