from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompt
from agent.tools.agent_tools import (
    rag_summarize,
    web_search,
    fill_context_for_report,
    fetch_external_data,
    python,
    matlab,
    store_memory,
    search_memory,
)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch


class ReactAgent:

    def __init__(self):
        self.agent = create_agent(
            model=chat_model,  
            tools=[
                rag_summarize,
                web_search,
                fill_context_for_report,
                fetch_external_data,
                python,
                matlab,
                store_memory,
                search_memory,
            ], 
            system_prompt= load_system_prompt(),
            middleware = [monitor_tool,log_before_model,report_prompt_switch],
        )

    def _needs_planning(self, query: str) -> bool:
        """Heuristic to trigger task decomposition for complex asks."""
        q = (query or "").strip()
        if len(q) >= 80:
            return True
        keywords = ["并且", "以及", "同时", "多个", "多步", "计划", "规划", "拆解", "步骤", "综合", "复杂"]
        return any(k in q for k in keywords)

    def _generate_plan(self, query: str) -> str:
        """Ask the chat model to break the goal into concise steps."""
        plan_prompt = (
            "你是任务规划器，负责将用户的复杂需求拆分为可执行子任务。\n"
            f"用户需求：{query}\n"
            "请给出不超过5步的拆解，覆盖输入目标，短句描述，每步独立可执行。\n"
            "输出格式示例：\n1) 子任务A\n2) 子任务B\n若无需拆解，则输出单步。"
        )
        plan = chat_model.invoke(plan_prompt)
        return getattr(plan, "content", str(plan))

    def execute_stream(self,query:str):
        messages = [{"role":"user","content":query}]

        if self._needs_planning(query):
            plan_text = self._generate_plan(query)
            planning_msg = f"任务规划：\n{plan_text}\n请按以上步骤逐步完成并在结束时汇总结果。"
            # 将规划注入对话上下文，帮助后续推理遵循步骤
            messages.append({"role":"assistant","content":planning_msg})
            # 同步向前端流式展示规划，便于用户感知
            yield planning_msg + "\n"

        input_dict = {"messages": messages}
        
        for chunk in self.agent.stream(input_dict,stream_mode="values",context={"report":False}):
            latest_message = chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip() + "\n"
