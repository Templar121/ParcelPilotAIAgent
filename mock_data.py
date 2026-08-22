# Contains knowledge base chunks, orders DataFrame, reference timestamps
import pandas as pd
from datetime import datetime

SNAPSHOT_TIME_STR = "2026-08-21 12:00:00"
SNAPSHOT_DATETIME = datetime.strptime(SNAPSHOT_TIME_STR, "%Y-%m-%d %H:%M:%S")

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