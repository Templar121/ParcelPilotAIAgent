import streamlit as st
import pandas as pd
import json
from datetime import datetime
from google import genai
from google.genai import types, errors

# -----------------------------------------------------------------------------
# 1. UI CONFIGURATION & SESSION CONTEXT
# -----------------------------------------------------------------------------
st.set_page_config(page_title="ParcelPilot AI Support", layout="wide")

st.sidebar.title("ParcelPilot Control Panel")
user_role = st.sidebar.radio("Select Role", ["CUSTOMER", "INTERNAL_OPS"])

if user_role == "CUSTOMER":
    account_id = st.sidebar.selectbox("Simulated Account", ["ACC-NORTHSTAR", "ACC-LUMENWORKS"])
    st.sidebar.caption(f"Authenticated as: **{account_id}**")
else:
    account_id = "INTERNAL_USER"
    st.sidebar.success("Internal Operations Mode: Global Access Enabled")

# Official assessment snapshot reference time
SNAPSHOT_TIME_STR = "2026-08-21 12:00:00"
SNAPSHOT_DATETIME = datetime.strptime(SNAPSHOT_TIME_STR, "%Y-%m-%d %H:%M:%S")
st.sidebar.info(f"System Snapshot Reference Time:\n**{SNAPSHOT_TIME_STR}**")

st.title("ParcelPilot AI Support & Operations")

# -----------------------------------------------------------------------------
# 2. STRUCTURED DATA & TIERED KNOWLEDGE BASE
# -----------------------------------------------------------------------------
KNOWLEDGE_BASE = [
    {
        "doc": "05_Northstar_Logistics_Enterprise_Agreement.pdf",
        "tier": 1,
        "account_id": "ACC-NORTHSTAR",
        "content": "Clause 4.2: Northstar may cancel dispatched orders up to 4 hours before scheduled pickup with zero cancellation fee. Overrides standard SOP fee schedules."
    },
    {
        "doc": "06_LumenWorks_Service_Agreement.pdf",
        "tier": 1,
        "account_id": "ACC-LUMENWORKS",
        "content": "Clause 3.1: LumenWorks receives a priority 4-hour SLA response and a 10% discount on expedited bookings."
    },
    {
        "doc": "03_Cancellation_and_Service_Credit_SOP_v4.pdf",
        "tier": 2,
        "account_id": "GLOBAL",
        "content": "Section 2: Standard cancellation of a DISPATCHED shipment incurs a $50 cancellation fee.\nSection 3: Late Pickup Credits (Carrier Fault): >= 2 hours late = 25% freight credit; >= 4 hours late = 50% freight credit. Requests must be escalated via support ticket."
    },
    {
        "doc": "01_Support_Policy_v3_CURRENT.pdf",
        "tier": 3,
        "account_id": "GLOBAL",
        "content": "Standard support operating hours are 24/7. Resolution SLA for standard priority issues is 24 hours."
    }
]

DB_ORDERS = pd.DataFrame([
    {
        "order_id": "ORD-1001",
        "account_id": "ACC-NORTHSTAR",
        "status": "DISPATCHED",
        "carrier": "SwiftHaul",
        "scheduled_pickup": "2026-08-21 16:00:00",
        "freight_charge": 450.00
    },
    {
        "order_id": "ORD-1002",
        "account_id": "ACC-LUMENWORKS",
        "status": "DELAYED",
        "carrier": "FreightFlow",
        "scheduled_pickup": "2026-08-21 09:00:00",
        "freight_charge": 620.00
    }
])

# -----------------------------------------------------------------------------
# 3. AGENT TOOLS (With RLS and Automated Datetime Math)
# -----------------------------------------------------------------------------
def search_documents(query: str) -> str:
    """Searches policy, agreement, and SOP documents. 
    Enforces privacy by restricting customer searches to global documents or their own agreement.
    
    Args:
        query: Topic or search terms (e.g., 'cancellation fee', 'service credit', 'SLA').
    """
    results = []
    for doc in KNOWLEDGE_BASE:
        if user_role == "CUSTOMER" and doc["account_id"] not in ["GLOBAL", account_id]:
            continue
        results.append(doc)
    
    # Sort strictly by priority (Tier 1 > Tier 2 > Tier 3)
    results = sorted(results, key=lambda x: x["tier"])
    
    output = "Retrieved Knowledge Base Documents:\n"
    for r in results:
        output += f"- [Tier {r['tier']} | {r['doc']}]: {r['content']}\n"
    return output

def query_structured_data(order_id: str) -> str:
    """Queries order details from the database and computes time deltas relative to the system snapshot time.
    
    Args:
        order_id: The identifier of the order (e.g., 'ORD-1001').
    """
    # Enforce Row-Level Security (RLS)
    if user_role == "CUSTOMER":
        matching = DB_ORDERS[(DB_ORDERS['order_id'] == order_id) & (DB_ORDERS['account_id'] == account_id)]
        if matching.empty:
            return json.dumps({
                "status": "ACCESS_DENIED",
                "message": f"Order '{order_id}' was not found or does not belong to your authenticated account ({account_id})."
            })
    else:
        matching = DB_ORDERS[DB_ORDERS['order_id'] == order_id]
        if matching.empty:
            return json.dumps({
                "status": "NOT_FOUND",
                "message": f"Order '{order_id}' does not exist in the database."
            })
            
    order_data = matching.iloc[0].to_dict()
    
    # Calculate exact time delta relative to SNAPSHOT_TIME
    try:
        scheduled_dt = datetime.strptime(order_data["scheduled_pickup"], "%Y-%m-%d %H:%M:%S")
        time_diff = scheduled_dt - SNAPSHOT_DATETIME
        hours_remaining = time_diff.total_seconds() / 3600.0
        
        order_data["reference_snapshot_time"] = SNAPSHOT_TIME_STR
        order_data["hours_until_scheduled_pickup"] = round(hours_remaining, 2)
        order_data["time_calculation_summary"] = (
            f"As of reference time {SNAPSHOT_TIME_STR}, there are exactly {round(hours_remaining, 2)} hours "
            f"remaining until scheduled pickup at {order_data['scheduled_pickup']}."
        )
    except Exception as e:
        order_data["time_calculation_error"] = str(e)
        
    return json.dumps(order_data)

def execute_action(action_type: str, details: str, confirmed: bool) -> str:
    """Creates an escalation ticket, processes a service credit, or cancels an order.
    
    Args:
        action_type: Type of action ('CREATE_ESCALATION_TICKET', 'PROCESS_CREDIT', 'CANCEL_ORDER').
        details: Specific details/rationale for the action.
        confirmed: MUST be False initially. Set to True ONLY after explicit human confirmation.
    """
    if not confirmed:
        return json.dumps({
            "status": "AWAITING_CONFIRMATION",
            "message": (
                f"Action draft created for: '{action_type}'. "
                f"Details: {details}. "
                "State to the user what action is proposed and ask for their explicit confirmation before proceeding."
            )
        })
    
    # Confirmed execution
    ticket_id = f"TICK-{datetime.now().strftime('%M%S')}"
    return json.dumps({
        "status": "COMPLETED",
        "ticket_id": ticket_id,
        "action_type": action_type,
        "message": f"Action successfully executed and recorded under Reference ID: {ticket_id}."
    })

# -----------------------------------------------------------------------------
# 4. AGENT INITIALIZATION & CHAT LOOP
# -----------------------------------------------------------------------------
if "client" not in st.session_state:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("Please configure 'GEMINI_API_KEY' in .streamlit/secrets.toml")
        st.stop()
        
    st.session_state.client = genai.Client(api_key=api_key)

# Re-create chat session if role/account changes to ensure isolated session context
current_context_key = f"{user_role}_{account_id}"
if "last_context_key" not in st.session_state or st.session_state.last_context_key != current_context_key:
    st.session_state.last_context_key = current_context_key
    st.session_state.messages = []
    
    system_prompt = f"""
You are the AI Support & Operations Agent for ParcelPilot.
Current Authenticated Context:
- User Role: {user_role}
- Account ID: {account_id}
- Dataset Reference Snapshot Time: {SNAPSHOT_TIME_STR}

STRICT OPERATIONAL GUIDELINES:
1. SOURCE HIERARCHY:
   - Tier 1: Customer-Specific Enterprise Agreements (ALWAYS overrides standard policies).
   - Tier 2: Standard Operating Procedures (Cancellation & Service Credit SOP).
   - Tier 3: General Support Policies.
   - Always cite the document name and Tier used to justify your answer.

2. ACCURATE DATETIME ARITHMETIC:
   - For cancellation windows or pickup timings, use the 'time_calculation_summary' and 'hours_until_scheduled_pickup' provided by the structured data tool.
   - Clearly state the current snapshot time ({SNAPSHOT_TIME_STR}), the scheduled time, and the exact hour difference.

3. PROACTIVE ACTION WORKFLOW (HUMAN-IN-THE-LOOP):
   - If a customer is entitled to a service credit, cancellation, or escalation, DO NOT just give policy information. 
   - Proactively call `execute_action(..., confirmed=False)` to draft the action, explain the prepared action to the user, and explicitly ask if they want to proceed.
   - Only call `execute_action(..., confirmed=True)` once the user gives clear confirmation (e.g., 'yes', 'confirm', 'proceed').

4. DATA PRIVACY & ACCESS CONTROL:
   - If `query_structured_data` returns ACCESS_DENIED, state clearly that the order does not exist or access is restricted for the current account.
"""

    st.session_state.chat_session = st.session_state.client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[search_documents, query_structured_data, execute_action],
            temperature=0.1,
        )
    )

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input Handling
if prompt := st.chat_input("Ask a question, check order status, or request a service action..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Processing request and executing tools..."):
            try:
                # Attempt to send the message to the model
                response = st.session_state.chat_session.send_message(prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
            except errors.APIError as e:
                # Specifically catch Google GenAI API errors
                if e.code == 429:
                    error_msg = (
                        "⚠️ **High Traffic Detected:** The AI is currently experiencing high demand "
                        "and has reached its free-tier rate limit. Please wait about 30 seconds and try again."
                    )
                    st.warning(error_msg)
                    # We remove the user's prompt from the history so it doesn't break the chat context turn order
                    st.session_state.messages.pop() 
                else:
                    st.error(f"⚠️ An API error occurred: {e.message}")
                    st.session_state.messages.pop()
                    
            except Exception as e:
                # Catch-all for any other unexpected Python errors
                st.error("⚠️ An unexpected system error occurred. Please try again.")
                # We remove the user's prompt from the history to maintain conversational sync
                st.session_state.messages.pop()