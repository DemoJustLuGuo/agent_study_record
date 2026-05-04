from pathlib import Path


def test_knowledge_tab_disables_public_gradio_api_names() -> None:
    source = Path("app/ui/knowledge_tab.py").read_text(encoding="utf-8")

    assert 'api_name="knowledge_' not in source
    assert source.count("api_name=False") >= 5
