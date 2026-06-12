# WellActually.ai 🧠🤖
### Domain-Driven Adversarial Code Review Swarm Center
*A multi-agent compliance & governance platform built on **Band.ai** and powered by **Featherless AI** & **AIML API**.*

---

## 🚀 Overview

**WellActually.ai** is an enterprise-grade adversarial code review and compliance swarm. It enforces **Zero-Trust compliance** policies by dynamically triaging code modifications, launching specialized LLM review swarms to validate changes against bounded contexts (database schemas & API specifications), and monitoring live runtime logs via an observability watchdog.

At the core of the system is the **Adversarial Swarm Debate**:
1. **Lead Coder Agent** (powered by `gpt-4o-mini` via AIML API) writes an order processing script. It attempts to insert data into a column that does not exist in the database (stubbornly persisting this error across revisions).
2. **Auth & Fraud SME Reviewer Agent** (powered by **Featherless AI's** `Llama-3.1-70B`) and **Cart SME Reviewer Agent** validate the implementation against the PostgreSQL schema and OpenAPI specifications.
3. If compliance checks fail, the Reviewers block the code (prefixed with `❌ REVIEW FAILED`).
4. **Consensus Tracker** counts iterations, automatically halting the loop on the 3rd round to trigger a **Human-in-the-Loop (HITL)** manual consent event.

---

## 🤝 Platform & Partner Stack Integrations

### 1. **Band.ai** (Core Agent Collaboration)
Our swarm is orchestrating real-time communication directly over the **Band.ai REST SDK** platform with zero safety fallbacks:
- **Identity & Registrations**: Registers Conductor, Coder, and Reviewer agents on the platform.
- **Chat Rooms & Participants**: Dynamically instantiates review rooms and adds agent participants with distinct roles.
- **Messages & Mentions**: Agents exchange context and code proposals using targeted `@mentions` (e.g., Coder mentioning Conductor, Reviewer mentioning Coder).
- **Context Rehydration**: Reviewers query the Chat Context endpoint before running evaluations to load the latest history.
- **Events**: Publishes custom chat error events to notify participants and human operators of deadlocks.
- **Memories**: The Band.ai platform limits the Memory API (saving/listing memories) strictly to Enterprise plans, throwing a `403 Forbidden` exception on other tiers. To solve this limitation, we implemented a robust programmatic local fallback database (writing/reading to `mock_infrastructure/local_memories.json`) which is activated dynamically upon catching `403` exceptions or when `BAND_MEMORY_MODE=local` is set in `.env` configurations. This preserves semantic memories across debate rounds without crashing.

### 2. **Featherless AI** (Sponsor Partner)
To leverage specialized open-source models at scale, we route the **Auth & Fraud SME Reviewer Agent** to the `unsloth/Meta-Llama-3.1-70B-Instruct` model hosted on **Featherless AI's** serverless endpoint (`https://api.featherless.ai/v1`). It performs strict SQL syntax verification, RBAC checks, and schema validation.

### 3. **AIML API** (Sponsor Partner)
All other agents in the swarm (the Conductor Orchestrator, the Lead Coder, and the Cart SME Reviewer) are routed via the **AIML API** gateway (`https://api.aimlapi.com/v1`) using the `gpt-4o-mini` model.

---

## 📂 Repository File Directory Structure

Every file in the repository plays a precise role in the Domain-Driven Governance engine:

### ⚙️ Core Swarm & Backend
- **[`src/swarm.py`](file:///c:/Users/vjbel/hacks/BOA/src/swarm.py)**: The async Swarm Orchestration library mapping python Agent classes to Band.ai REST SDK endpoints. It implements the **Agent Reuse Mechanism** (detecting if the workspace is near the 10-agent limit and reusing pre-registered credentials) and routes Auth SME reviews to Featherless AI.
- **[`src/server.py`](file:///c:/Users/vjbel/hacks/BOA/src/server.py)**: A FastAPI server exposing REST endpoints to manage swarm state, events, manual HITL overrides, and logs. It feeds the web dashboard in real-time.
- **[`src/governance.py`](file:///c:/Users/vjbel/hacks/BOA/src/governance.py)**: The deterministic compliance and validation engine:
  - `parse_codeowners`: Parses CODEOWNERS directives and matches modified paths.
  - `triage_pr`: Halts the auto-merge loop and forces state to `PENDING_HUMAN_APPROVAL` if high-stakes paths (like `/src/auth/` or `/src/billing/`) are touched.
  - `ConsensusTracker`: Monitors rounds and flags a deadlock on the 3rd iteration.
  - `verify_schema_compliance` / `verify_openapi_compliance`: Compares code blocks against Postgres schemas and OpenAPI endpoints (acting as static MCP checks).
  - `TelemetryScanner`: Log stream watchdog parser scanning for memory leaks and database connection pool exhaustion.
- **[`src/githooks/compliance_hook.py`](file:///c:/Users/vjbel/hacks/BOA/src/githooks/compliance_hook.py)**: A Git pre-commit hook enforcing compliance triage locally.
- **[`install_hooks.py`](file:///c:/Users/vjbel/hacks/BOA/install_hooks.py)**: Automates installation of git pre-commit hooks.

### 💻 Frontend Web Dashboard
- **[`frontend/src/App.jsx`](file:///c:/Users/vjbel/hacks/BOA/frontend/src/App.jsx)**: React Swarm Control Center dashboard. It polls FastAPI server state and provides an interactive interface displaying the PR Board, static MCP checks, Watchdog alerts, Slack-like debate room feed, and manual HITL consent overrides. Includes a dedicated container-level `.scrollTop` scroll mechanic that prevents browser window scroll hijacking.
- **[`frontend/src/index.css`](file:///c:/Users/vjbel/hacks/BOA/frontend/src/index.css)**: Custom dark-themed CSS system incorporating rich glassmorphism panel styling, glowing neon indicators (red for violations, green for compliance), and micro-animations.

### 🧪 Tests & Mocks
- **[`tests/test_swarm.py`](file:///c:/Users/vjbel/hacks/BOA/tests/test_swarm.py)**: Comprehensive test suite verifying all governance checks (CODEOWNERS matching, consensus rounds, watchdog leaks) and mocking the `AsyncRestClient` interface.
- **[`mock_infrastructure/`](file:///c:/Users/vjbel/hacks/BOA/mock_infrastructure)**:
  - `postgres_schema.sql`: Postgres checkout database structure.
  - `openapi_contract.json`: OpenAPI spec details for `/api/v1/checkout`.
  - `app_logs.json`: Mock application log stream containing connection pool exhaustion and memory leak signatures.
  - `CODEOWNERS`: Swarm ownership rules defining high-stakes paths.

### 📜 Component Demo Scripts
- **[`demo_swarm_execution.py`](file:///c:/Users/vjbel/hacks/BOA/demo_swarm_execution.py)**: Console-based CLI review simulation using `rich` panels.
- **[`demo_triage_and_hook.py`](file:///c:/Users/vjbel/hacks/BOA/demo_triage_and_hook.py)**: Demonstrates the pre-commit hook and CODEOWNERS path triage matching.
- **[`demo_mcp_verification.py`](file:///c:/Users/vjbel/hacks/BOA/demo_mcp_verification.py)**: Simulates schema mismatches and OpenAPI contract failures.
- **[`demo_telemetry_watchdog.py`](file:///c:/Users/vjbel/hacks/BOA/demo_telemetry_watchdog.py)**: Scans log streams and triggers alert blocks when telemetry warnings are found.

---

## 🛠️ Installation & Setup

Ensure you have Node.js and Python installed. Activate your virtual environment and configure your `.env`:

```ini
BAND_API_KEY=band_u_...
OPENAI_API_KEY=...             # AIML API key
FEATHERLESS_API_KEY=rc_...      # Featherless AI key
GH_TOKEN=github_pat_...
```

### 1. Install dependencies
```powershell
# Python packages
uv pip install fastapi uvicorn openai httpx pyyaml pydantic python-dotenv pytest anyio sse-starlette rich

# Frontend packages
cd frontend
npm.cmd install
```

### 2. Run Tests
Verify everything is working:
```powershell
.venv\Scripts\python.exe -m pytest
```

---

## 🖥️ How to Run the Swarm Control Center

1. **Start the FastAPI Backend Server**:
   ```powershell
   .venv\Scripts\python.exe -m uvicorn src.server:app --reload --port 8000
   ```
2. **Start the React Frontend Dashboard**:
   ```powershell
   cd frontend
   npm.cmd run dev
   ```
3. Open your browser and navigate to `http://localhost:5173`.
4. Click **Start Swarm Review** and observe:
   - Zero-trust compliance triage matches billing files and halts execution.
   - Click **Approve Exception** to launch the swarm agents.
   - Watch the chat feed pull remote rooms, rehydrate context, and route reviews dynamically to **Featherless AI**.
   - Notice the expected memory limit crash-out which triggers the `CRASHED` state on the dashboard (as no safety fallbacks are allowed).
