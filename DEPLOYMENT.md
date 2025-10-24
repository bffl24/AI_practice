# 🚀 HMM Call Preparation Agent – Deployment Guide

## Overview
This guide outlines deployment steps for the HMM Call Preparation Agent using Google ADK and GCP Vertex AI.  
Deployments are managed through Apigee-proxied, authenticated endpoints for secure runtime access.  
Both Non-Production and Production configurations are supported.

---

## ⚙️ Pre-Requisites

### 1. Python Environment
```bash
python --version   # Must be >= 3.12.10
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# OR
source .venv/bin/activate        # macOS/Linux
pip install -r requirements.txt
```

---

### 2. GCloud CLI Setup
```bash
gcloud init
gcloud config configurations list
```

Set up Application Default Credentials (ADC):  
```bash
gcloud auth application-default login
```

If you see a quota mismatch warning:
```bash
gcloud auth application-default set-quota-project direct-landing-436217-q4
```

---

## 🧩 Non-Production Deployment (UAT / Sandbox)

```python
"""
Deployment Script - Non-Prod Environment
Deploys HMM Call Preparation Agent to ADK Engine (Sandbox/UAT)
"""

import os
from google.adk.deploy import deploy_agent

# --- Environment Variables ---
os.environ["GOOGLE_CLOUD_PROJECT"] = "direct-landing-436217-q4"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
os.environ["ADK_ENV"] = "nonprod"
os.environ["APIGEE_BASE_URL"] = "https://apigee.bcbsma-cloud.com/v1/hmm/uat"
os.environ["APIGEE_API_KEY"] = "your_nonprod_apigee_key"

# --- Agent Deployment ---
if __name__ == "__main__":
    deploy_agent(
        agent_package_path="app/root_agent",
        display_name="HMM_Call_Prep_Agent_NonProd",
        description="HMM Call Preparation Agent - Non-Production Deployment",
    )
```

Run deployment:
```bash
python deploy_np.py
```

Validate deployment:
```bash
adk web
```

---

## 🏭 Production Deployment

```python
"""
Deployment Script - Production Environment
Deploys HMM Call Preparation Agent to ADK Engine (Production)
"""

import os
from google.adk.deploy import deploy_agent

# --- Environment Variables ---
os.environ["GOOGLE_CLOUD_PROJECT"] = "bcbsma-prod-ai-436217"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
os.environ["ADK_ENV"] = "prod"
os.environ["APIGEE_BASE_URL"] = "https://apigee.bcbsma-cloud.com/v1/hmm/prod"
os.environ["APIGEE_API_KEY"] = "your_prod_apigee_key"

# --- Agent Deployment ---
if __name__ == "__main__":
    deploy_agent(
        agent_package_path="app/root_agent",
        display_name="HMM_Call_Prep_Agent_Prod",
        description="HMM Call Preparation Agent - Production Deployment",
    )
```

Run deployment:
```bash
python deploy.py
```

Verify deployment in GCP Vertex AI Console or via ADK CLI:
```bash
adk web
```

---

## 🧠 Post-Deployment Validation Checklist

| ✅ Checkpoint | Description |
|----------------|-------------|
| **1. Agent visibility** | Confirm the agent appears under ADK `adk web` dashboard |
| **2. Environment** | Ensure correct environment tag (Non-Prod / Prod) is active |
| **3. API connectivity** | Validate Apigee endpoint access and key authentication |
| **4. LLM output test** | Run a sample prompt and verify summary formatting |
| **5. Logs & telemetry** | Check logs in GCP Logging for agent activity and latency |

---

## 🔒 Security & Compliance Notes
- All API traffic routes via Apigee proxy with OAuth / API key-based authentication.  
- ADC credentials must be refreshed every 30 days.  
- Rotate `APIGEE_API_KEY` and service account keys periodically.  
- Ensure `.env` files are never committed to Git.
