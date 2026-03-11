from langchain.agents import create_agent
from langchain_siliconflow import ChatSiliconFlow
from langchain.tools import tool

@tool(description="获取体重")
def get_weight() -> int:
    return 65

@tool(description="获取身高")
def get_height() -> int:
    return 175
    
agent = create_agent(
    model=ChatSiliconFlow(model="Pro/MiniMaxAI/MiniMax-M2.5"),
    tools=[get_weight,get_height],
    system_prompt="你是一个严格遵循ReAct范式的聊天助手，必须按【思考】【行动】【观察】【思考】的流程解决问题，并且每轮只能调用一个工具，禁止单次调用多个工具。告知我你的思考和行动，工具的调用原因，直到你得出结论并回答用户的问题。",
)

for chunk in agent.stream(
    {
        "messages":[{"role":"user","content":"请帮我算算BMI是多少？"}]
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

        