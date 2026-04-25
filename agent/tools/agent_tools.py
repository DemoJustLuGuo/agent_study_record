"""工具兼容导出层。

历史上所有工具函数都集中定义在本文件。
当前已拆分到 agent.tools.modules 下的独立源码中，
并由 agent.tools.registry 统一注册管理。
本文件保留同名导出，避免旧代码导入路径失效。
"""

from agent.tools.modules.compute_tools import matlab, python
from agent.tools.modules.context_tools import fill_context_for_report
from agent.tools.modules.memory_tools import search_memory, store_memory
from agent.tools.modules.rag_tools import rag_summarize
from agent.tools.modules.web_tools import web_search
from agent.tools.registry import (
    get_registered_tool_entries,
    get_registered_tool_map,
    get_registered_tool_names,
    register_tools,
)

__all__ = [
    "rag_summarize",
    "web_search",
    "fill_context_for_report",
    "python",
    "matlab",
    "store_memory",
    "search_memory",
    "register_tools",
    "get_registered_tool_entries",
    "get_registered_tool_map",
    "get_registered_tool_names",
]
