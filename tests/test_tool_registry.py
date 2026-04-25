from langchain_core.tools import BaseTool

from agent.tools.registry import (
    get_registered_tool_entries,
    get_registered_tool_map,
    get_registered_tool_names,
    register_tools,
)


EXPECTED_TOOL_NAMES = [
    "rag_summarize",
    "web_search",
    "fill_context_for_report",
    "python",
    "matlab",
    "store_memory",
    "search_memory",
]


def test_registered_tool_names_are_stable() -> None:
    assert get_registered_tool_names() == EXPECTED_TOOL_NAMES


def test_registered_tool_entries_are_valid() -> None:
    seen: set[str] = set()

    for entry in get_registered_tool_entries():
        assert entry.name not in seen
        seen.add(entry.name)

        assert isinstance(entry.tool, BaseTool)
        assert entry.tool.name == entry.name
        assert entry.tool.args_schema is not None
        assert (entry.tool.description or "").strip()
        assert entry.category in {"knowledge", "web", "context", "compute", "memory"}
        assert entry.risk in {"safe", "network", "high"}
        assert entry.description.strip()


def test_register_tools_returns_registry_order() -> None:
    assert [tool.name for tool in register_tools()] == EXPECTED_TOOL_NAMES
    assert list(get_registered_tool_map()) == EXPECTED_TOOL_NAMES
