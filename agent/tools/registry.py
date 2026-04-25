from dataclasses import dataclass
from typing import Literal

from langchain_core.tools import BaseTool

from agent.tools.modules.compute_tools import matlab, python
from agent.tools.modules.context_tools import fill_context_for_report
from agent.tools.modules.memory_tools import search_memory, store_memory
from agent.tools.modules.rag_tools import rag_summarize
from agent.tools.modules.web_tools import web_search

ToolCategory = Literal["knowledge", "web", "context", "compute", "memory"]
ToolRisk = Literal["safe", "network", "high"]


@dataclass(frozen=True)
class ToolRegistryEntry:
    """Registry metadata for a single LangChain tool."""

    name: str
    tool: BaseTool
    category: ToolCategory
    risk: ToolRisk
    description: str


_TOOL_ENTRIES: tuple[ToolRegistryEntry, ...] = (
    ToolRegistryEntry(
        name="rag_summarize",
        tool=rag_summarize,
        category="knowledge",
        risk="safe",
        description="Query the local RAG knowledge base for stable project or domain context.",
    ),
    ToolRegistryEntry(
        name="web_search",
        tool=web_search,
        category="web",
        risk="network",
        description="Search public web sources for current or external communication-system facts.",
    ),
    ToolRegistryEntry(
        name="fill_context_for_report",
        tool=fill_context_for_report,
        category="context",
        risk="safe",
        description="Inject report-mode context before producing formal deliverables.",
    ),
    ToolRegistryEntry(
        name="python",
        tool=python,
        category="compute",
        risk="high",
        description="Run Python calculations, data processing, or communication simulations.",
    ),
    ToolRegistryEntry(
        name="matlab",
        tool=matlab,
        category="compute",
        risk="high",
        description="Run MATLAB or Octave-style matrix and signal-processing calculations.",
    ),
    ToolRegistryEntry(
        name="store_memory",
        tool=store_memory,
        category="memory",
        risk="safe",
        description="Persist stable user preferences or project facts into long-term memory.",
    ),
    ToolRegistryEntry(
        name="search_memory",
        tool=search_memory,
        category="memory",
        risk="safe",
        description="Retrieve relevant long-term memory for user or project context.",
    ),
)


def _validate_tool_entries(entries: tuple[ToolRegistryEntry, ...]) -> None:
    seen: set[str] = set()
    for entry in entries:
        if entry.name in seen:
            raise ValueError(f"Duplicate tool registration: {entry.name}")
        seen.add(entry.name)

        if not isinstance(entry.tool, BaseTool):
            raise TypeError(f"Registered object is not a BaseTool: {entry.name}")
        if entry.tool.name != entry.name:
            raise ValueError(
                f"Tool registry name mismatch: {entry.name} != {entry.tool.name}"
            )
        if entry.tool.args_schema is None:
            raise ValueError(f"Tool args_schema is required: {entry.name}")
        if not (entry.tool.description or "").strip():
            raise ValueError(f"Tool description is required: {entry.name}")
        if not entry.description.strip():
            raise ValueError(f"Registry description is required: {entry.name}")


_validate_tool_entries(_TOOL_ENTRIES)

_REGISTERED_TOOLS: dict[str, BaseTool] = {
    entry.name: entry.tool for entry in _TOOL_ENTRIES
}


def register_tools() -> list[BaseTool]:
    return list(_REGISTERED_TOOLS.values())


def get_registered_tool_map() -> dict[str, BaseTool]:
    return dict(_REGISTERED_TOOLS)


def get_registered_tool_names() -> list[str]:
    return list(_REGISTERED_TOOLS.keys())


def get_registered_tool_entries() -> tuple[ToolRegistryEntry, ...]:
    return _TOOL_ENTRIES
