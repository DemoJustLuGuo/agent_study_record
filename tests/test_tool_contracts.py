from agent.tools.modules.compute_tools import python
from agent.tools.modules.context_tools import fill_context_for_report
from agent.tools.modules.memory_tools import search_memory, store_memory
from agent.tools.modules.rag_tools import rag_summarize
from agent.tools.modules.shared import format_tool_failure
from agent.tools.modules.web_tools import web_search
from agent.tools.registry import get_registered_tool_map


def _schema_fields(tool_name: str) -> set[str]:
    schema = get_registered_tool_map()[tool_name].args_schema
    fields = getattr(schema, "model_fields", getattr(schema, "__fields__", {}))
    return set(fields)


def test_tool_schema_fields_are_explicit() -> None:
    assert _schema_fields("rag_summarize") == {"query"}
    assert _schema_fields("web_search") == {"query"}
    assert _schema_fields("fill_context_for_report") == set()
    assert _schema_fields("python") == {"code"}
    assert _schema_fields("matlab") == {"code"}
    assert _schema_fields("store_memory") == {"note", "user_id", "scope", "project"}
    assert _schema_fields("search_memory") == {"query", "user_id", "project"}


def test_fill_context_for_report_invokes_without_args() -> None:
    result = fill_context_for_report.invoke({})

    assert "fill_context_for_report" in result
    assert "报告上下文" in result


def test_empty_python_code_returns_failure_contract() -> None:
    result = python.invoke({"code": ""})

    assert result.startswith("【失败】python调用失败")
    assert "原因：代码为空" in result


def test_empty_web_query_returns_failure_contract_without_network() -> None:
    result = web_search.invoke({"query": ""})

    assert result.startswith("【失败】web_search调用失败")
    assert "原因：查询为空" in result


def test_empty_rag_query_returns_failure_contract_without_backend() -> None:
    result = rag_summarize.invoke({"query": ""})

    assert result.startswith("【失败】rag_summarize调用失败")
    assert "原因：查询为空" in result


def test_empty_memory_inputs_return_failure_contract_without_backend() -> None:
    store_result = store_memory.invoke({"note": ""})
    search_result = search_memory.invoke({"query": ""})

    assert store_result.startswith("【失败】store_memory调用失败")
    assert "原因：记忆内容为空" in store_result
    assert search_result.startswith("【失败】search_memory调用失败")
    assert "原因：查询为空" in search_result


def test_format_tool_failure_contract() -> None:
    result = format_tool_failure(
        tool_name="example_tool",
        reason="输入无效",
        solution="补充必填参数",
    )

    assert (
        result == "【失败】example_tool调用失败\n原因：输入无效\n解决方案：补充必填参数"
    )
