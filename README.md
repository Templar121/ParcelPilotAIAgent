# ParcelPilot AI Support & Operations Agent

This project is a modular, AI-powered customer support and operations agent built for ParcelPilot. It demonstrates advanced LLM capabilities including multi-step tool execution (ReAct loops), deterministic priority resolution for conflicting policies, and strict Row-Level Security (RLS) applied directly at the tool layer.

Powered by **Streamlit** (for the UI) and **Groq** (using Meta's Llama 3 models or OpenAI's open-weights models for lightning-fast inference).

## Repository Structure

```text
parcelpilot-ai/
├── .streamlit/
│   └── secrets.toml          # API keys (Create this locally, ignored by git)
├── .gitignore                # Ensures secrets aren't pushed to GitHub
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
├── mock_data.py              # Knowledge base docs, DB mocks, and timestamps
├── tools.py                  # Functional tools (RLS privacy & datetime math)
├── prompts.py                # System instruction templates
└── app.py                    # Streamlit frontend & agentic loop
```

## Setup and Run Instructions

### 1. Prerequisites
- Python 3.10 or higher
- Groq API Key.

### 2. Clone the Repository
```bash
git clone [https://github.com/YOUR_USERNAME/parcelpilot-ai.git](https://github.com/YOUR_USERNAME/parcelpilot-ai.git)
cd parcelpilot-ai
```

### 3. Create a Virtual Environment (Windows)
```bash
python -m venv venv
venv\Scripts\activate
```
### 4. Install Dependencies
```bash
pip install -r requirements.txt
```
### 5. Setup your API Key (Streamlit Secrets)
- In the root directory, create a hidden folder named .streamlit.
- Inside that folder, create a file named secrets.toml.
- Add your Groq API key to the file:

```bash
GROQ_API_KEY = "gsk_YOUR_GROQ_KEY_HERE"
```
### 6. Run the Application
```bash
streamlit run app.py
```