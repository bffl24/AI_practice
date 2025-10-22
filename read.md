HMM Call Preparation Agent
Overview

The HMM Call Preparation Agent is a Gen AI–driven healthcare assistant built using Google’s Agent Development Kit (ADK).
It automates the process of retrieving, validating, and summarizing patient data to support care managers during Health Management Model (HMM) outreach calls.

The agent interacts with Apigee proxy–enabled API endpoints, providing secure, compliant, and real-time access to patient data.
It applies structured summarization prompts to generate concise, accurate, and clinically relevant summaries for care coordination teams.

Core Components

Root Agent – Orchestrates user queries, manages session context, and delegates to sub-agents.

Sub-Agent (hmm_call_prep) – Handles patient data retrieval via Apigee-enabled APIs.

Prompt (prompt.py) – Defines structured clinical summarization rules and format.

Tool (hmm_get_data) – Connects to API aggregator services, retrieves, validates, and transforms patient data.

Apigee Gateway – Provides a secure interface layer between internal Gen AI agents and enterprise data APIs.

Folder Structure
CALL-PREP/
├── .venv/
├── app/
│   ├── agent/
│   │   ├── deployment/
│   │   │   ├── deploy.py
│   │   │   ├── deploy_np.py
│   │   │   ├── utils.py
│   │   │   └── .env.deploy
│   │
│   ├── root_agent/
│   │   ├── agent.py
│   │   ├── prompt.py
│   │   ├── config.py
│   │   ├── config.yaml
│   │   └── .env.testagent
│   │
│   ├── sub_agents/
│   │   └── hmm_call_prep/
│   │       ├── tools/
│   │       │   ├── client.py
│   │       │   ├── aggregator.py
│   │       │   └── __init__.py
│   │       ├── agent.py
│   │       ├── prompt.py
│   │       ├── .env
│   │       └── AGENT_README.md
│   │
│   └── api/
│       └── test_agent.py
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md

Key Features

- Autonomous Data Orchestration – Dynamically identifies patient context and retrieves relevant information.
- Apigee Proxy Integration – Secure connection through enterprise API gateway ensuring controlled access and audit compliance.
- Session Context Preservation – Maintains patient identifiers, ensuring multi-turn continuity.
- Structured Summarization – Converts raw API payloads into human-readable clinical summaries.
- Asynchronous Workflow – Supports parallel API requests for scalable execution.
- Modular Multi-Agent Design – Enables easy addition of future agents (e.g., pharmacy insights, claims review).

Setup and Installation
1. Prerequisites

Python 3.12.10

Google ADK installed (pip install google-adk)

Apigee access credentials and authorized endpoints

Vertex AI or Gemini API access (for LLM inference)

2. Environment Setup
python -m venv .venv
source .venv/bin/activate     # macOS/Linux
.venv\Scripts\Activate.ps1    # Windows PowerShell
pip install -r requirements.txt

3. Environment Variables

Rename .env.example to .env and configure as below:

GOOGLE_API_KEY=your_api_key_here
GOOGLE_CLOUD_PROJECT=your_project_id
GOOGLE_CLOUD_LOCATION=us-central1
APIGEE_BASE_URL=https://apigee.bcbsma-cloud.com/v1/hmm
APIGEE_API_KEY=your_apigee_key

Running / Testing the Agent
Option  – ADK Web Interface
adk web --------> change directory to agent folder then start 


Access the agent at http://localhost:8000
, select hmm_call_prep, and interact via chat.


Data Flow Overview

User Query → Root Agent: Captures subscriber ID, patient name, and context.

Delegation → Sub-Agent: The hmm_call_prep agent triggers the hmm_get_data tool.

Apigee Proxy Call: Authenticated requests are routed through Apigee to internal data APIs.

Data Aggregation: aggregator.py merges data (demographics, meds, visits, and status).

Prompt Execution: prompt.py formats the final output as a structured clinical summary.

Response Delivery: Output is displayed in the ADK Web UI or returned via API.

Troubleshooting Guide
Issue	Possible Cause	Resolution
Agent not visible in adk web	Incorrect __init__.py import or folder structure	Ensure __init__.py imports agent correctly and root_agent folder name matches
API request failing (401/403)	Missing or invalid Apigee API key	Regenerate key and verify with Apigee console
“No data returned”	API endpoint unavailable or payload format mismatch	Verify Apigee proxy routing and schema alignment
LLM output inconsistent	Prompt misalignment or missing fields	Check prompt.py format consistency and ensure aggregator returns required keys
High latency in responses	Parallel calls not awaited properly	Review async/await usage inside hmm_get_data and aggregator methods
“Unknown Agent” on startup	ADK not discovering the agent	Run adk web from the parent directory, not inside the agent folder
Data mismatch across sessions	Context state not persisted	Check session handling in ADK Runner or InMemorySessionService
Vertex AI auth failure	Missing credentials	Run gcloud auth application-default login and validate project ID
Version Control & Deployment

Branch: main

Deployment Config: deploy.py, .env.deploy

Cloud Runtime: GCP Vertex AI (through ADK runtime)

Telemetry: Integrated via Python logging and ADK context logs

Security: All API interactions go through Apigee-proxied, authenticated endpoints

License

This project is internal to BCBSMA and follows organizational data governance, privacy, and compliance standards.
