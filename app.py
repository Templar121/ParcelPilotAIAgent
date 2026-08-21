import streamlit as st
import pandas as pd
import json
from datetime import datetime
from google import genai
from google.genai import types

# -----------------------------------------------------------------------------
# 1. UI CONFIGURATION & SESSION CONTEXT
# -----------------------------------------------------------------------------
st.set_page_config(page_title="ParcelPilot AI", layout="wide")

st.sidebar.title("System Configuration")
user_role = st.sidebar.radio("Select Role", ["CUSTOMER", "INTERNAL_OPS"])
if user_role == "CUSTOMER":
    # Global variable picked up by the tool functions during execution
    account_id = st.sidebar.selectbox("Simulate Account", ["ACC-NORTHSTAR", "ACC-LUMENWORKS"])
else:
    account_id = "INTERNAL_USER"
    st.sidebar.info("Internal Ops Mode: Global Data Access Enabled.")
    
st.title("ParcelPilot Support Agent (Powered by Gemini)")

# -----------------------------------------------------------------------------
# 2. MOCK DATA (Replace with actual data loading in production)
# -----------------------------------------------------------------------------
SNAPSHOT_TIME = datetime(2026, 8, 21, 12, 0)

KNOWLEDGE_BASE = [
    {"doc": "05_Northstar_Logistics_Enterprise_Agreement.pdf", "tier": 1, "account_id": "ACC-NORTHSTAR", "content": "Northstar may cancel dispatched orders up to 4 hours before pickup with zero cancellation fee."},
    {"doc": "06_LumenWorks_Service_Agreement.pdf", "tier": 1, "account_id": "ACC-LUMENWORKS", "content": "LumenWorks receives a 10% discount on all expedited shipments."},
    {"doc": "03_Cancellation_and_Service_Credit_SOP_v4.pdf", "tier": 2, "account_id": "GLOBAL", "content": "Late Pickup Credits: >= 2 hours late carrier fault = 25% credit. >= 4 hours late = 50% credit. Standard cancellation post-dispatch incurs a $50 fee."},
    {"doc": "01_Support_Policy_v3_CURRENT.pdf", "tier": 3, "account_id": "GLOBAL", "content": "Standard SLA for resolving normal priority tickets is 24 hours."},
]

DB_ORDERS = pd.DataFrame([
    {"order_id": "ORD-1001", "account_id": "ACC-NORTHSTAR", "status": "DISPATCHED", "carrier": "SwiftHaul", "scheduled_pickup": "2026-08-21 16:00:00"},
    {"order_id": "ORD-1002", "account_id": "ACC-LUMENWORKS", "status": "DELAYED", "carrier": "FreightFlow", "scheduled_pickup": "2026-08-21 09:00:00"}
])

# -----------------------------------------------------------------------------
# 3. AGENT TOOLS (Privacy & Authority Enforced at the Python Layer)
# -----------------------------------------------------------------------------
def search_documents(query: str) -> str:
    """Searches the knowledge base for policy and agreement documents based on the query.
    
    Args:
        query: The search term or topic (e.g., 'cancellation fee', 'late pickup credit').
    """
    results = []
    for doc in KNOWLEDGE_BASE:
        # RLS / Privacy check: Only return GLOBAL docs or docs belonging to the user's account
        if user_role == "CUSTOMER" and doc["account_id"] not in ["GLOBAL", account_id]:
            continue
        results.append(doc)
    
    # Sort by authority tier (1 is highest priority)
    results = sorted(results, key=lambda x: x["tier"])
    
    response = "Sources found:\n"
    for r in results:
        response += f"- [Tier {r['tier']} | {r['doc']}]: {r['content']}\n"
    return response

def query_structured_data(order_id: str) -> str:
    """Queries the structured database for order details and SLA status.
    
    Args:
        order_id: The exact ID of the order (e.g., 'ORD-1001').
    """
    # RLS / Privacy Enforcement
    if user_role == "CUSTOMER":
        order = DB_ORDERS[(DB_ORDERS['order_id'] == order_id) & (DB_ORDERS['account_id'] == account_id)]
    else: 
        # INTERNAL_OPS can see everything
        order = DB_ORDERS[DB_ORDERS['order_id'] == order_id]
        
    if order.empty:
        return json.dumps({"error": "Order not found or access denied for this account."})
    
    return order.to_json(orient="records")

def execute_action(action_type: str, details: str, confirmed: bool) -> str:
    """Performs a state-changing action like creating a ticket or processing a credit.
    
    Args:
        action_type: The action name (e.g., 'Create Escalation Ticket', 'Process Credit').
        details: Details or payload for the action.
        confirmed: MUST be False initially. Set to True ONLY if the user explicitly confirms the action.
    """
    if not confirmed:
        # Rejects the action and forces Gemini to ask the user for confirmation
        return json.dumps({"status": "PENDING_CONFIRMATION", "message": f"Draft prepared for {action_type}. Tell the user the details and explicitly ask for their confirmation to proceed."})
    
    # Mocking the actual database commit
    return json.dumps({"status": "SUCCESS", "message": f"Action '{action_type}' committed successfully."})

# -----------------------------------------------------------------------------
# 4. GEMINI AGENT INITIALIZATION & CHAT LOOP
# -----------------------------------------------------------------------------
if "client" not in st.session_state:
    # Safely retrieve the API key from Streamlit secrets
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("Missing GEMINI_API_KEY in Streamlit secrets. Please configure it.")
        st.stop()
        
    st.session_state.client = genai.Client(api_key=api_key) 
    
if "chat_session" not in st.session_state:
    st.session_state.chat_session = st.session_state.client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are ParcelPilot's AI Support Agent. You have access to tools to search documents, "
                "lookup structured order data, and execute state-changing actions.\n"
                "- ALWAYS prioritize Tier 1 Custom Agreements over Tier 2 or 3 policies.\n"
                "- Cite your sources using the Document Name and Tier.\n"
                "- If a tool requires confirmation, call execute_action with confirmed=False, "
                "explain the action to the user, and wait for their human reply before calling it again with confirmed=True."
            ),
            tools=[search_documents, query_structured_data, execute_action],
            temperature=0.2,
        )
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("How can I help you today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing request and utilizing tools..."):
            try:
                # The Gemini SDK automatically triggers the Python tools when the model requests them
                response = st.session_state.chat_session.send_message(prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Error calling Gemini API: {str(e)}")