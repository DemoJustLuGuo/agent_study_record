import streamlit as st
from agent.tools.react_agent import ReactAgent

#标题
st.title("RAG Agent 演示")
st.divider()

if "agent" not in st.session_state:
    st.session_state.agent = ReactAgent()

if "messages" not in st.session_state:
    st.session_state["message"] = []
    
for message in st.session_state["message"]:
    st.chat_message(message["role"]).write(message["content"])
    
#用户输入提示词
prompt = st.chat_input("请输入您的问题：")

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role":"user","content":prompt})

    response_messages = []
    with st.spinner("智能体正在思考..."):
        res_stream = st.session_state["agent"].execute_stream(prompt)

        def capture(generator, cache_list):
            for chunk in generator:
                cache_list.append(chunk)
                yield chunk

        st.chat_message("assistant").write_stream(capture(res_stream, response_messages))
        st.session_state["message"].append({"role":"assistant","content": response_messages[-1]})
