# Contains streamlit UI, session state, & Gemini client loop
import streamlit as st
import json
from groq import Groq
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

# Initialize Groq Client
if "client" not in st.session_state:
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except KeyError:
        st.error("Please configure 'GROQ_API_KEY' in .streamlit/secrets.toml")
        st.stop()
    st.session_state.client = Groq(api_key=api_key)

# Session state management
current_context_key = f"{user_role}_{account_id}"
if "last_context_key" not in st.session_state or st.session_state.last_context_key != current_context_key:
    st.session_state.last_context_key = current_context_key
    st.session_state.messages = []

# Define Tool Schemas for Groq (OpenAI format)
GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Searches policy, agreement, and SOP documents.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search topic"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_structured_data",
            "description": "Queries order details from the database and computes SLA time deltas.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "The exact ID of the order (e.g., ORD-1001)"}},
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_action",
            "description": "Creates an escalation ticket, processes a service credit, or cancels an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_type": {"type": "string"},
                    "details": {"type": "string"},
                    "confirmed": {"type": "boolean", "description": "MUST be false initially. Set to true ONLY if user explicitly confirmed."}
                },
                "required": ["action_type", "details", "confirmed"]
            }
        }
    }
]

# Render Chat
for msg in st.session_state.messages:
    if msg["role"] != "system" and msg["role"] != "tool" and not msg.get("tool_calls"):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Chat Input & Loop
if prompt := st.chat_input("Ask a question, check order status, or request a service action..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Processing request..."):
            try:
                # 1. Build conversation history
                system_instruction = get_system_prompt(user_role, account_id, SNAPSHOT_TIME_STR)
                messages_payload = [{"role": "system", "content": system_instruction}] + st.session_state.messages
                
                # 2. Initial Call to Groq
                response = st.session_state.client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=messages_payload,
                    tools=GROQ_TOOLS,
                    tool_choice="auto",
                    temperature=0.1
                )
                
                response_message = response.choices[0].message
                
                # 3. Agentic Loop: Keep executing tools as long as the model requests them (max 5 steps)
                MAX_STEPS = 5
                step_count = 0
                
                while response_message.tool_calls and step_count < MAX_STEPS:
                    step_count += 1
                    
                    # Append the AI's tool request to our history
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "tool_calls": [t.model_dump() for t in response_message.tool_calls],
                        "content": response_message.content or ""
                    })
                    messages_payload.append(response_message)
                    
                    # Execute every tool requested in this step
                    for tool_call in response_message.tool_calls:
                        fn_name = tool_call.function.name
                        try:
                            args = json.loads(tool_call.function.arguments)
                            if fn_name == "search_documents":
                                tool_result = search_documents(args.get("query", ""))
                            elif fn_name == "query_structured_data":
                                tool_result = query_structured_data(args.get("order_id", ""))
                            elif fn_name == "execute_action":
                                tool_result = execute_action(
                                    args.get("action_type", ""), 
                                    args.get("details", ""), 
                                    args.get("confirmed", False)
                                )
                            else:
                                tool_result = f"Error: Unknown function {fn_name}"
                        except Exception as e:
                            tool_result = f"Error processing tool call: {str(e)}"
                            
                        # Add the execution result to the conversation
                        tool_msg = {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": fn_name,
                            "content": str(tool_result)
                        }
                        st.session_state.messages.append(tool_msg)
                        messages_payload.append(tool_msg)
                    
                    # Trigger the next Groq call to analyze the tool results
                    next_response = st.session_state.client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=messages_payload,
                        tools=GROQ_TOOLS,
                        temperature=0.1
                    )
                    response_message = next_response.choices[0].message
                
                # 4. Once the loop finishes (no more tools), output the final text
                final_text = response_message.content if response_message.content else "I have completed the task."
                
                st.markdown(final_text)
                st.session_state.messages.append({"role": "assistant", "content": final_text})
                    
            except Exception as e:
                st.error(f"⚠️ An error occurred: {str(e)}")
                # Remove failed prompt to keep history clean
                if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
                    st.session_state.messages.pop()