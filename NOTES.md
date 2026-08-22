## Architecture Note

### Agent Design

The application uses a custom stateful ReAct (Agentic) Loop powered by the Groq API and open-weights models. Instead of relying on a black-box SDK for execution, the orchestrator utilizes a while loop that can dynamically chain multiple tool calls together in a single conversational turn (e.g., querying a database $\rightarrow$ searching documents $\rightarrow$ staging an action) before returning a synthesized answer to the user.

### Tool Design & Access Control

Privacy and multi-tenancy are enforced strictly at the Python tool layer, never relying on prompt engineering for security. The session context (user_role and account_id) is injected programmatically into the tool execution layer. When tools like query_structured_data() are called, they apply Row-Level Security (RLS) via pandas filters. This ensures a CUSTOMER can only ever retrieve rows matching their account, instantly returning an ACCESS_DENIED state if they attempt to query a different tenant's data.

### Document, Structured-Data Handling, & Source Reliability

To address conflicting data (Problem 2), the system implements a Deterministic Priority Resolver. Every knowledge base chunk is tagged with an authority_tier:

- Tier 1: Customer-Specific Agreements (Overrides all policies).
- Tier 2: Standard Operating Procedures.
- Tier 3: General Policies.

During RAG retrieval, context is strictly sorted and presented by tier so custom clauses always override general SLA guidelines. For structured data, datetime arithmetic (e.g., calculating hours until pickup against the snapshot timestamp) is calculated programmatically inside the Python tool and passed to the LLM to prevent arithmetic hallucinations.

### Major Technical Trade-offs

1. Deterministic Math vs. LLM Math: Rather than asking the LLM to calculate percentage fees or remaining hours, these calculations are hardcoded in the data retrieval tool. This guarantees 100% accuracy for financial/SLA math but requires slightly more backend logic.

2. Tool-Level Security vs. DB-Level RLS: For this assessment, RLS was implemented using in-memory Python/pandas filters for portability. In a production environment, this would be shifted down to the database level using dedicated PostgreSQL service roles.

## Product Note

### Addressing the Additional Client Problem

I chose to address Problem 1: Proactive Issue Detection. While this assessment focuses on the reactive chatbot interface, the architecture supports an "Internal Ops Mode." In a production environment, I would deploy a background asynchronous worker (e.g., a Cron job) that utilizes the LLM's JSON extraction capabilities to run root-cause analysis over new tickets. It would cluster these tickets by carrier_id or geography and push proactive alerts to a dashboard (e.g., "Warning: FreightFlow pickups are trending 40% later than the 7-day average in the Northeast"), allowing operations to intervene before customers complain.

### Future Product Additions

If I were continuing to build ParcelPilot, my next priorities would be:

1. Automated Carrier Dispute Settlement: Once an SLA breach is confirmed and a credit is issued to a customer, the system automatically fires a webhook to the carrier's API to file a dispute claim and recoup the cost.

2. Contract Diff Monitoring: An ingestion pipeline that automatically indexes customer contract renewals and flags support managers if custom SLA clauses (Tier 1 rules) have changed.

### What I Intentionally Left Out

I omitted standing up a live vector database (e.g., Pinecone/ChromaDB) and PDF OCR extraction pipelines. Instead, I mocked the parsed document chunks and structured tables. This ensures the submitted codebase is extremely lightweight, immediately runnable locally or on Streamlit Cloud, and entirely focused on demonstrating agentic reasoning, tool routing, and security.

### North Star Metric

The primary metric to judge the product's usefulness is the First-Contact Resolution (FCR) Rate, tracked specifically alongside a Zero-Reversal Rate. A high FCR combined with zero manual rollbacks (where a human operations agent has to undo a credit or action taken by the AI) proves that the system is both autonomous and deeply trusted by the business.

### AI Tool Usage

I utilized AI coding assistants (such as Google Gemini/ChatGPT) as a pair-programming partner during this assessment. Specifically, I used AI to:

1. Rapidly scaffold the Streamlit UI components and session state logic.

2. Generate the mock pandas DataFrames to closely simulate the provided Excel data structure.

3. Brainstorm and refine the Python logic for the ReAct while loop to ensure the agent could cleanly handle multi-step reasoning without dropping tool call arguments.

All core business logic—specifically the Row-Level Security privacy filters, the authority tiering architecture, and the Human-In-The-Loop confirmation state machine—was explicitly designed and hand-reviewed by me to guarantee strict compliance with the assessment parameters.