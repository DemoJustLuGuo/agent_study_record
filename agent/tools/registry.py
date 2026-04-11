from langchain_core.tools import BaseTool

from agent.tools.modules.compute_tools import matlab, python
from agent.tools.modules.context_tools import fill_context_for_report
from agent.tools.modules.memory_tools import search_memory, store_memory
from agent.tools.modules.rag_tools import rag_summarize
from agent.tools.modules.web_tools import web_search

_REGISTERED_TOOLS: dict[str, BaseTool] = {
    "rag_summarize": rag_summarize,
    "web_search": web_search,
    "fill_context_for_report": fill_context_for_report,
    "python": python,
    "matlab": matlab,
    "store_memory": store_memory,
    "search_memory": search_memory,
}


def register_tools() -> list[BaseTool]:
    return list(_REGISTERED_TOOLS.values())


def get_registered_tool_map() -> dict[str, BaseTool]:
    return dict(_REGISTERED_TOOLS)


def get_registered_tool_names() -> list[str]:
    return list(_REGISTERED_TOOLS.keys())
