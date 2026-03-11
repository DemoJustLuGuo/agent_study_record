from langchain.agents import create_agent
from langchain_siliconflow import ChatSiliconFlow
from langchain_core.tools import tool

@tool(description="获取现在的准确时间，返回字符串信息")
def get_time() -> str:
    return "现在的时间是2024年1月12日 12:00:00"

@tool(description="获取现在的新闻，传入现在的准确时间，返回字符串信息")
def get_news(time:str) -> str:
    return f"{time}的新闻是："

agent = create_agent(
    model=ChatSiliconFlow(model="Pro/MiniMaxAI/MiniMax-M2.5"),
    tools=[get_news,get_time],
    system_prompt="你是一个聊天助手,可以回答用户的问题，并且可以调用工具获取信息。",
)

for chunk in agent.stream(
    {
        "messages":[
            {"role":"user","content":"今天的新闻是什么？"}
        ]
    },
    stream_mode="values"
):
   latest_message = chunk["messages"][-1]

   if latest_message.content:
    print(type(latest_message).__name__,latest_message.content)

    try:
        if latest_message.tool_calls:
            print(f"工具调用:{[tc['name']for tc in latest_message.tool_calls]}")
    except AttributeError as e:
        pass