from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompt
from agent.tools.agent_tools import rag_summarize,get_weather,get_user_location,get_user_id,get_current_month,fill_context_for_report,fetch_external_data,python,matlab
from agent.tools.middleware import monitor_tool,log_before_model,report_prompt_switch


class ReactAgent:

    def __init__(self):
        self.agent = create_agent(
            model=chat_model,  
            tools=[rag_summarize,get_weather,get_user_location,get_user_id,get_current_month,fill_context_for_report,fetch_external_data,python,matlab], 
            system_prompt= load_system_prompt(),
            middleware = [monitor_tool,log_before_model,report_prompt_switch],
        )


    def execute_stream(self,query:str):
        input_dict = {
            "messages": [
                {"role":"user","content":query},
            ]
        }
        
        for chunk in self.agent.stream(input_dict,stream_mode="values",context={"report":False}):
            latest_message = chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip() + "\n"
