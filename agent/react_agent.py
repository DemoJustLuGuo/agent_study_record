from __future__ import annotations

import re
import uuid

from langchain.agents import create_agent

from agent.middleware import (
    log_after_model,
    log_before_model,
    log_model_call,
    monitor_tool,
    report_prompt_switch,
)
from agent.tools.registry import get_registered_tool_map, register_tools
from model.factory import chat_model
from utils.log import logger
from utils.prompt_loader import load_system_prompt


class ReactAgent:
    """
    Agent 编排器：
    - RAG 作为工具（rag_summarize / web_search）
    - 计算作为工具（python / matlab）
    - 先做轻量路由（查书/算数/混合），可选任务拆解
    """

    def __init__(self) -> None:
        self.tools_map = get_registered_tool_map()
        self.inline_tool_names = set(self.tools_map.keys())
        self.agent = create_agent(
            model=chat_model,
            tools=register_tools(),
            system_prompt=load_system_prompt(),
            middleware=[
                monitor_tool,
                log_model_call,
                log_before_model,
                log_after_model,
                report_prompt_switch,
            ],
        )

    # ---------- routing & planning ----------
    def _route_strategy(self, query: str) -> str:
        q = (query or "").lower()
        math_kw = ["计算", "评估", "大小", "比例", "率", "%", "数值", "方程", "概率", "可能性", "公式", "结果是多少"]
        info_kw = ["什么", "介绍", "解释", "原理", "历史", "文献", "资料", "参考", "知识", "信息", "定义"]
        has_math = any(k in q for k in math_kw)
        has_info = any(k in q for k in info_kw)
        if has_math and not has_info:
            return "compute"
        if has_info and not has_math:
            return "lookup"
        if has_info and has_math:
            return "mixed"
        return "lookup"

    def _strategy_message(self, strategy: str) -> str:
        if strategy == "compute":
            return "决策：先“算数”（python/matlab），如需背景再用 rag_summarize。"
        if strategy == "mixed":
            return "决策：先“查书”（rag_summarize / web_search），再“算数”（python/matlab）。"
        return "决策：先“查书”（rag_summarize 或 web_search），如出现计算再转用 python/matlab。"

    def _needs_planning(self, query: str) -> bool:
        q = (query or "").strip()
        if len(q) >= 80:
            return True
        keywords = ["并且", "以及", "同时", "多个", "多步", "计划", "规划", "拆解", "步骤", "综合", "复杂"]
        return any(k in q for k in keywords)

    def _generate_plan(self, query: str) -> str:
        plan_prompt = (
            "你是任务规划器，负责将用户的复杂需求拆分为可执行子任务。\n"
            f"用户需求：{query}\n"
            "请给出不超过5步的拆解，短句描述，若无需拆解则输出单步。"
        )
        plan = chat_model.invoke(plan_prompt)
        return getattr(plan, "content", str(plan))

    def _parse_inline_tool(self, reasoning: str):
        """
        Minimal parser for Minimax-style inline tool call markup:
        <invoke name="tool"><parameter name="foo">bar</parameter></invoke>
        Returns (tool_name, kwargs dict) or (None, None) if not found.
        """
        if not reasoning:
            return None, None
        invoke_match = re.search(r'<invoke name="([^"]+)">(.+?)</invoke>', reasoning, re.S | re.I)
        if not invoke_match:
            return None, None
        tool_name = invoke_match.group(1).strip()
        body = invoke_match.group(2)
        params = {}
        for m in re.finditer(r'<parameter name="([^"]+)">(.*?)</parameter>', body, re.S | re.I):
            params[m.group(1).strip()] = m.group(2).strip()
        return tool_name, params

    # ---------- streaming entry ----------
    def execute_stream(self, query: str):
        trace_id = uuid.uuid4().hex[:8]
        logger.info(f"[react_agent][{trace_id}] received query")
        messages = [{"role": "user", "content": query}]
        sent_contents: set[str] = set()

        # 1) 路由提示
        strategy = self._route_strategy(query)
        strategy_msg = self._strategy_message(strategy)
        # 仅记录日志，不向前端输出，避免干扰用户和模型
        logger.debug(f"[react_agent][{trace_id}] strategy={strategy}")

        # 2) 复杂请求 -> 任务拆解
        if self._needs_planning(query):
            plan_text = self._generate_plan(query)
            planning_msg = f"任务规划：\n{plan_text}\n请按以上步骤逐步完成，并在结束时总结结果。"
            # 仅记录日志，不输出到前端
            logger.debug(f"[react_agent][{trace_id}] plan len={len(plan_text)}")

        # 3) ReAct 流程
        input_dict = {"messages": messages}
        try:
            for chunk in self.agent.stream(
                input_dict, stream_mode="values", context={"report": False, "trace_id": trace_id}
            ):
                latest_message = chunk["messages"][-1]
                text = (getattr(latest_message, "content", None) or "").strip()

                if not text:
                    reasoning = None
                    try:
                        reasoning = getattr(latest_message, "additional_kwargs", {}).get("reasoning_content")
                    except Exception:
                        pass
                    if reasoning:
                        tool_name, params = self._parse_inline_tool(str(reasoning))
                        if tool_name and tool_name in self.inline_tool_names:
                            try:
                                tool_func = self.tools_map[tool_name]
                                result = tool_func(**params) if params else tool_func()
                                text = f"[{tool_name} result]\n{result}"
                            except Exception as tool_exc:
                                logger.error(f"[react_agent][{trace_id}] inline tool {tool_name} failed: {tool_exc}")
                                text = f"[tool_error] {tool_name}: {tool_exc}"
                        if not text:
                            text = str(reasoning).strip()

                if not text:
                    tool_calls = getattr(latest_message, "tool_calls", None)
                    if tool_calls:
                        text = f"[tool_call] {tool_calls}"

                if not text:
                    if isinstance(latest_message, dict):
                        text = str(latest_message)
                    else:
                        text = str(latest_message)

                if not text or text in sent_contents:
                    logger.debug(f"[react_agent][{trace_id}] skip duplicate/empty chunk")
                    continue
                sent_contents.add(text)
                logger.debug(f"[react_agent][{trace_id}] chunk len={len(text)}")
                yield text + "\n"
        except Exception as exc:
            logger.error(f"[react_agent][{trace_id}] stream failed: {exc}")
            yield f"[ERROR] {exc}"
