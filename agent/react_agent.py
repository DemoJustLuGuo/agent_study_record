from __future__ import annotations

import re
import uuid
from typing import Any

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

    def _extract_tool_names(self, tool_calls: Any) -> list[str]:
        names: list[str] = []

        if isinstance(tool_calls, list):
            for item in tool_calls:
                name = None
                if isinstance(item, dict):
                    name = item.get("name")
                else:
                    name = getattr(item, "name", None)
                    if name is None and hasattr(item, "get"):
                        try:
                            name = item.get("name")
                        except Exception:
                            name = None
                if name:
                    names.append(str(name))
        else:
            text = str(tool_calls or "")
            names.extend(re.findall(r"['\"]name['\"]\s*:\s*['\"]([^'\"]+)['\"]", text))

        unique_names: list[str] = []
        for name in names:
            if name not in unique_names:
                unique_names.append(name)
        return unique_names

    def _tool_call_summary(self, tool_calls: Any) -> str:
        names = self._extract_tool_names(tool_calls)
        if not names:
            return "[THINK] 正在调用工具处理请求。"
        return f"[THINK] 正在调用工具：{', '.join(names)}。"

    def _normalize_stream_text(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""

        if cleaned.startswith("[tool_call]"):
            payload = cleaned.removeprefix("[tool_call]").strip()
            return self._tool_call_summary(payload)

        if cleaned.startswith("[tool_error]"):
            detail = cleaned.removeprefix("[tool_error]").strip()
            if detail:
                return f"[THINK] 工具调用失败：{detail}"
            return "[THINK] 工具调用失败。"

        if re.match(r"^\[[^\]]+\s+result\]", cleaned, re.I):
            return "[THINK] 已收到工具输出，正在整理结论。"

        if re.match(r"^(Q:|A:)", cleaned):
            return f"[THINK] {cleaned}"

        return cleaned

    def _summarize_inline_tool_result(self, query: str, tool_name: str, params: dict[str, Any], result: Any) -> str:
        params_preview = str(params)
        result_preview = str(result)
        if len(params_preview) > 600:
            params_preview = params_preview[:600] + "..."
        if len(result_preview) > 4000:
            result_preview = result_preview[:4000] + "..."

        prompt = (
            "你是通信系统助手。请基于工具输出给出面向用户的最终回答。\n"
            "请严格遵守：\n"
            "1) 第一行必须以‘结论：’开头，给出直接答案；\n"
            "2) 后续补充不超过3条依据或说明；\n"
            "3) 禁止输出代码、JSON、tool_call、Q:/A:、内部思考。\n\n"
            f"用户问题：{query}\n"
            f"工具名称：{tool_name}\n"
            f"工具参数：{params_preview}\n"
            f"工具输出：\n{result_preview}"
        )

        try:
            response = chat_model.invoke(prompt)
            content = (getattr(response, "content", None) or str(response)).strip()
            if content:
                return content
        except Exception as exc:
            logger.error(f"inline tool summarize failed: {exc}")

        return "结论：已完成工具计算，但暂时无法自动整理结论，请展开思考过程查看明细。"

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
                text = self._normalize_stream_text((getattr(latest_message, "content", None) or "").strip())

                if not text:
                    reasoning = None
                    try:
                        reasoning = getattr(latest_message, "additional_kwargs", {}).get("reasoning_content")
                    except Exception:
                        pass
                    if reasoning:
                        tool_name, params = self._parse_inline_tool(str(reasoning))
                        if tool_name and tool_name in self.inline_tool_names:
                            tool_start_msg = f"[THINK] 正在调用工具：{tool_name}。"
                            if tool_start_msg not in sent_contents:
                                sent_contents.add(tool_start_msg)
                                logger.debug(f"[react_agent][{trace_id}] chunk len={len(tool_start_msg)}")
                                yield tool_start_msg + "\n"

                            try:
                                tool_func = self.tools_map[tool_name]
                                invoke_args = params or {}
                                if hasattr(tool_func, "invoke"):
                                    result = tool_func.invoke(invoke_args)
                                elif callable(tool_func):
                                    result = tool_func(**invoke_args) if invoke_args else tool_func()
                                else:
                                    raise RuntimeError(f"tool {tool_name} is not invokable")

                                tool_done_msg = f"[THINK] 工具 {tool_name} 执行完成，正在整理结论。"
                                if tool_done_msg not in sent_contents:
                                    sent_contents.add(tool_done_msg)
                                    logger.debug(f"[react_agent][{trace_id}] chunk len={len(tool_done_msg)}")
                                    yield tool_done_msg + "\n"

                                final_text = self._summarize_inline_tool_result(
                                    query=query,
                                    tool_name=tool_name,
                                    params=invoke_args,
                                    result=result,
                                )
                                final_text = self._normalize_stream_text(final_text)
                                if final_text and final_text not in sent_contents:
                                    sent_contents.add(final_text)
                                    logger.debug(f"[react_agent][{trace_id}] chunk len={len(final_text)}")
                                    yield final_text + "\n"
                                return
                            except Exception as tool_exc:
                                logger.error(f"[react_agent][{trace_id}] inline tool {tool_name} failed: {tool_exc}")
                                text = f"[THINK] 工具 {tool_name} 执行失败：{tool_exc}"
                        if not text:
                            text = "[THINK] 正在分析问题并整理答案。"

                if not text:
                    tool_calls = getattr(latest_message, "tool_calls", None)
                    if tool_calls:
                        text = self._tool_call_summary(tool_calls)

                if not text:
                    continue

                if not text or text in sent_contents:
                    logger.debug(f"[react_agent][{trace_id}] skip duplicate/empty chunk")
                    continue
                sent_contents.add(text)
                logger.debug(f"[react_agent][{trace_id}] chunk len={len(text)}")
                yield text + "\n"
        except Exception as exc:
            logger.error(f"[react_agent][{trace_id}] stream failed: {exc}")
            yield f"[ERROR] {exc}"
