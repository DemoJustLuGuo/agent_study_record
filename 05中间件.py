from langchain.agents import create_agent,AgentState
from langchain_siliconflow import ChatSiliconFlow
from langchain.tools import tool
from langchain.agents.middleware import before_agent,after_agent,before_model,after_model,wrap_model_call,wrap_tool_call
from langgraph.runtime import Runtime

@tool(description="查询天气，传入城市名称字符串，返回字符串天气信息")
def get_weather(city: str) -> str:
    return f"{city}的天气是晴天"

@before_agent #agent执行前
def log_before_agent(state:AgentState,runtime:Runtime) -> None:
    print(f"[before_agent]开始了agent的执行，并附带了{len(state.get('messages', []))}条消息和{len(state.get('tool_calls', []))}次工具调用的状态")

@after_agent #agent执行后
def log_after_agent(state:AgentState,runtime:Runtime) -> None:
    print(f"[after_agent]结束了agent的执行，并附带了{len(state.get('messages', []))}条消息和{len(state.get('tool_calls', []))}次工具调用的状态")

@before_model #model执行前
def log_before_model(state:AgentState,runtime:Runtime) -> None:
    print(f"[before_model]开始了model的执行，并附带了{len(state.get('messages',[]))}条消息和{len(state.get('tool_calls',[]))}次工具调用的状态")

@after_model #model执行后
def log_after_model(state:AgentState,runtime:Runtime) -> None:
    print(f"[after_model]结束了model的执行，并附带了{len(state.get('messages',[]))}条消息和{len(state.get('tool_calls',[]))}次工具调用的状态")

@wrap_model_call  #模型执行中
def model_call_hook(request,handler):
    print("模型已调用！")
    return handler(request)

@wrap_tool_call  #工具执行中
def monitor_tool(request,handler):
    print(f"工具执行：{request.tool_call['name']}")
    print(f"工具执行传参：{request.tool_call['args']}")
    return handler(request)

agent = create_agent(
    model=ChatSiliconFlow(model="Pro/MiniMaxAI/MiniMax-M2.5"),
    tools=[get_weather],
    system_prompt="你是一个聊天助手,可以回答用户的问题，并且可以调用工具获取信息。",
    middleware=[log_before_agent,log_after_agent,log_before_model,log_after_model,model_call_hook,monitor_tool]
)

res = agent.invoke(
    {
        "messages":[{"role":"user","content":"今天天气如何？"}]
    },
)

print("*************\n",res)