import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

st.title("Personal Learning Tutor")

llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

if "messages" not in st.session_state:
    st.session_state.messages = [
        SystemMessage(content="You are a personal learning tutor. Your job is to teach concepts clearly, use examples, and ask follow-up questions to check understanding.")
    ]

# Display chat history
for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.write(msg.content)
    elif not isinstance(msg, SystemMessage):
        with st.chat_message("assistant"):
            st.write(msg.content)

# Chat input
if prompt := st.chat_input("Ask me to teach you something..."):
    st.session_state.messages.append(HumanMessage(content=prompt))
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = llm.invoke(st.session_state.messages)
        st.write(response.content)
        st.session_state.messages.append(response)
