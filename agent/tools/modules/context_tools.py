from langchain_core.tools import tool
from pydantic import BaseModel


class FillContextForReportArgs(BaseModel):
    """该工具无入参，仅用于触发报告模式上下文切换。"""


@tool(
    args_schema=FillContextForReportArgs,
    description=(
        "触发报告模式上下文切换。无入参；当用户要求生成报告、方案、"
        "可交付文档或正式分析时调用，后续模型调用会切换到报告提示词。"
    ),
)
def fill_context_for_report() -> str:
    """触发中间件将后续模型调用切换到报告提示词。"""
    return "fill_context_for_report已经调用，报告上下文已补充"
