from html import unescape
from urllib.parse import quote
import xml.etree.ElementTree as ET

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agent.tools.modules.shared import (
    format_tool_failure,
    load_text_from_url,
    truncate_output,
)
from utils.log import logger

WEB_SEARCH_TIMEOUT_SECONDS = 15
BING_CN_SEARCH_URL = "https://cn.bing.com/search?q="


class WebSearchArgs(BaseModel):
    query: str = Field(
        description=(
            "公开网络检索关键词，建议 2-20 个词。用于标准、术语、参数范围、"
            "行业资料和实时事实核验；查询为空时返回可解释失败信息。"
        )
    )


def _parse_bing_rss_items(rss_text: str, max_items: int = 5) -> list[str]:
    try:
        root = ET.fromstring(rss_text)
    except ET.ParseError as exc:
        logger.warning(f"必应RSS解析失败: {str(exc)}")
        return []

    snippets: list[str] = []
    items = root.findall("./channel/item")

    rank = 1
    for item in items:
        if rank > max_items:
            break

        title = unescape((item.findtext("title") or "").strip())
        link = unescape((item.findtext("link") or "").strip())
        desc = unescape((item.findtext("description") or "").strip())

        title = " ".join(title.split())
        desc = " ".join(desc.split())
        link = " ".join(link.split())

        if not title:
            continue

        if desc and link:
            snippets.append(f"{rank}. {title} - {desc} ({link})")
        elif desc:
            snippets.append(f"{rank}. {title} - {desc}")
        elif link:
            snippets.append(f"{rank}. {title} ({link})")
        else:
            snippets.append(f"{rank}. {title}")
        rank += 1

    return snippets


@tool(
    args_schema=WebSearchArgs,
    description=(
        "联网搜索公开信息并返回前几条摘要结果。用于通信标准、术语、"
        "参数范围、行业资料和实时事实的快速核验；当前实现使用必应中国 RSS。"
    ),
)
def web_search(query: str) -> str:
    """通过必应中国 RSS 检索公开网页摘要。"""
    query = (query or "").strip()
    if not query:
        return format_tool_failure(
            tool_name="web_search",
            reason="查询为空",
            solution="请提供明确的联网检索关键词后重试。",
        )

    bing_rss_url = BING_CN_SEARCH_URL + quote(query) + "&format=rss&setlang=zh-cn"
    rss_text = load_text_from_url(bing_rss_url, timeout=WEB_SEARCH_TIMEOUT_SECONDS)
    if rss_text is None:
        return format_tool_failure(
            tool_name="web_search",
            reason="联网请求失败",
            solution="请检查网络连通性或代理设置，稍后重试；也可先使用本地知识库工具。",
        )

    snippets = _parse_bing_rss_items(rss_text, max_items=5)
    if not snippets:
        return "【成功】web_search已执行（必应中国RSS），但未检索到可用摘要结果"

    return truncate_output("\n".join(snippets))
