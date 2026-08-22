# Contains streamlit UI, session state, & Gemini client loop
import streamlit as st
from google import genai
from google.genai import types, errors
from mock_data import SNAPSHOT_TIME_STR
from tools import search_documents, query_structured_data, execute_action, set_tool_context
from prompts import get_system_prompt

st.set_page_config(page_title="ParcelPilot AI Support", layout="wide")

# Sidebar Configuration
st.sidebar.title("ParcelPilot Control Panel")
user_role = st.sidebar.radio("Select Role", ["CUSTOMER", "INTERNAL_OPS"])

if user_role == "CUSTOMER":
    account_id = st.sidebar.selectbox("Simulated Account", ["ACC-NORTHSTAR", "ACC-LUMENWORKS"])
    st.sidebar.caption(f"Authenticated as: **{account_id}**")
else:
    account_id = "INTERNAL_USER"
    st.sidebar.success("Internal Operations Mode: Global Access Enabled")

st.sidebar.info(f"System Snapshot Reference Time:\n**{SNAPSHOT_TIME_STR}**")
st.title("ParcelPilot AI Support & Operations")

# Sync tool context with selected UI role/account
set_tool_context(user_role, account_id)

# Initialize Gemini Client
if "client" not in st.session_state:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("Please configure 'GEMINI_API_KEY' in .streamlit/secrets.toml")
        st.stop()
    st.session_state.client = genai.Client(api_key=api_key)

# Session state reset on context change
current_context_key = f"{user_role}_{account_id}"
if "last_context_key" not in st.session_state or st.session_state.last_context_key != current_context_key:
    st.session_state.last_context_key = current_context_key
    st.session_state.messages = []
    
    st.session_state.chat_session = st.session_state.client.chats.create(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(
            system_instruction=get_system_prompt(user_role, account_id, SNAPSHOT_TIME_STR),
            tools=[search_documents, query_structured_data, execute_action],
            temperature=0.1,
        )
    )

# Render Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input & Safe Error Handling
if prompt := st.chat_input("Ask a question, check order status, or request a service action..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Processing request and executing tools..."):
            try:
                response = st.session_state.chat_session.send_message(prompt)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except errors.APIError as e:
                if e.code == 429:
                    st.warning("⚠️ **High Traffic:** Free-tier rate limit reached. Please wait ~30 seconds and try again.")
                else:
                    st.error(f"⚠️ API Error: {e.message}")
                st.session_state.messages.pop()
            except Exception as e:
                st.error("⚠️ An unexpected error occurred. Please try again.")
                st.session_state.messages.pop()