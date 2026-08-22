# Contains tool functions (with RLS privacy & datetime math)
import json
from datetime import datetime
from mock_data import KNOWLEDGE_BASE, DB_ORDERS, SNAPSHOT_DATETIME, SNAPSHOT_TIME_STR

# Global contextual state updated dynamically by app.py
current_context = {
    "user_role": "CUSTOMER",
    "account_id": "ACC-NORTHSTAR"
}

def set_tool_context(role: str, acc_id: str):
    """Updates the execution context for tool-layer access control."""
    current_context["user_role"] = role
    current_context["account_id"] = acc_id

def search_documents(query: str) -> str:
    """Searches policy, agreement, and SOP documents. 
    Enforces privacy by restricting customer searches to global documents or their own agreement.
    
    Args:
        query: Topic or search terms (e.g., 'cancellation fee', 'service credit', 'SLA').
    """
    user_role = current_context["user_role"]
    account_id = current_context["account_id"]

    results = []
    for doc in KNOWLEDGE_BASE:
        if user_role == "CUSTOMER" and doc["account_id"] not in ["GLOBAL", account_id]:
            continue
        results.append(doc)
    
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
    user_role = current_context["user_role"]
    account_id = current_context["account_id"]

    # Row-Level Security
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
    
    try:
        scheduled_dt = datetime.strptime(order_data["scheduled_pickup"], "%Y-%m-%d %H:%M:%S")
        time_diff = scheduled_dt - SNAPSHOT_DATETIME
        hours_remaining = round(time_diff.total_seconds() / 3600.0, 2)
        
        order_data["reference_snapshot_time"] = SNAPSHOT_TIME_STR
        order_data["hours_until_scheduled_pickup"] = hours_remaining
        order_data["time_calculation_summary"] = (
            f"As of reference time {SNAPSHOT_TIME_STR}, there are exactly {hours_remaining} hours "
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
    
    ticket_id = f"TICK-{datetime.now().strftime('%M%S')}"
    return json.dumps({
        "status": "COMPLETED",
        "ticket_id": ticket_id,
        "action_type": action_type,
        "message": f"Action successfully executed and recorded under Reference ID: {ticket_id}."
    })