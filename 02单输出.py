from langchain.agents import create_agent
from langchain_siliconflow import ChatSiliconFlow
from langchain_core.tools import tool

@tool(description="获取天气信息")
def get_weather(location: str) -> str:
    return f"{location}的天气晴朗，温度25度。"

agent = create_agent(
    model=ChatSiliconFlow(model="Pro/MiniMaxAI/MiniMax-M2.5"),
    tools=[get_weather],
    system_prompt="你是一个聊天助手,可以回答用户的问题，并且可以调用工具获取信息。",
)

res = agent.invoke(
    {
        "messages":[
            {"role":"user","content":"明天深圳的天气怎么样？"}
        ]
    }
)
for message in res["messages"]:
    print(type(message).__name__,message.content)
