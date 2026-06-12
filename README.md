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
Our swarm orchestrates real-time communication directly over the **Band.ai REST SDK** platform:
- **Identity & Registrations**: Registers Conductor, Coder, and Reviewer agents on the platform.
- **Chat Rooms & Participants**: Dynamically instantiates review rooms and adds agent participants with distinct roles.
- **Messages & Mentions**: Agents exchange context and code proposals using targeted `@mentions` (e.g., Coder mentioning Conductor, Reviewer mentioning Coder).
- **Context Rehydration**: Reviewers query the Chat Context endpoint before running evaluations to load the latest history.
- **Events**: Publishes custom chat error events to notify participants and human operators of deadlocks.
- **Agent Reuse Mechanism**: Automatically detects the platform's 10-agent limit and reuses pre-registered agent credentials (loaded from environment variables) to prevent registration failures.
- **Memories (Local Fallback)**: The Band.ai Memory API is limited to Enterprise plans, throwing `403 Forbidden` on Free/Pro tiers. We implemented a robust programmatic local fallback (writing/reading to `mock_infrastructure/local_memories.json`) which is activated dynamically upon catching `403` exceptions or when `BAND_MEMORY_MODE=local` is set in `.env`. This preserves semantic memories across debate rounds with zero crashes.

### 2. **Featherless AI** (Hackathon Sponsor Partner)
To leverage specialized open-source models at scale, we route the **Auth & Fraud SME Reviewer Agent** to the `unsloth/Meta-Llama-3.1-70B-Instruct` model hosted on **Featherless AI's** serverless endpoint (`https://api.featherless.ai/v1`). It performs strict SQL syntax verification, RBAC checks, and schema validation. The Featherless AI integration ensures our adversarial pairing uses genuinely different model architectures (Llama 3.1 vs GPT-4o) to maximize review diversity.

### 3. **AIML API** (Hackathon Sponsor Partner)
All other agents in the swarm (the Conductor Orchestrator, the Lead Coder, and the Cart SME Reviewer) are routed via the **AIML API** gateway (`https://api.aimlapi.com/v1`) using the `gpt-4o-mini` model. By redirecting `OPENAI_BASE_URL` to the AIML API endpoint, we achieve seamless integration with the sponsor's infrastructure while maintaining standard OpenAI client compatibility.

---

## 📂 Repository File Directory Structure

Every file in the repository plays a precise role in the Domain-Driven Governance engine:

### ⚙️ Core Swarm & Backend
| File | Description |
|------|-------------|
| [`src/swarm.py`](src/swarm.py) | Async Swarm Orchestration library mapping Python Agent classes to Band.ai REST SDK endpoints. Implements the **Agent Reuse Mechanism** (detecting if the workspace is near the 10-agent limit and reusing pre-registered credentials) and routes Auth SME reviews to Featherless AI. |
| [`src/server.py`](src/server.py) | FastAPI server exposing REST endpoints (`/api/status`, `/api/events`, `/api/start`, `/api/consent`, `/api/telemetry`, `/api/mcp`) to manage swarm state, events, manual HITL overrides, and logs. Feeds the web dashboard in real-time. |
| [`src/governance.py`](src/governance.py) | The deterministic compliance and validation engine — `parse_codeowners`, `triage_pr`, `ConsensusTracker`, `verify_schema_compliance`, `verify_openapi_compliance`, and `TelemetryScanner`. |
| [`src/githooks/compliance_hook.py`](src/githooks/compliance_hook.py) | Git pre-commit hook enforcing compliance triage locally. Blocks commits touching high-stakes paths. |
| [`install_hooks.py`](install_hooks.py) | Automates installation of the git pre-commit compliance hook. |

### 💻 Frontend Web Dashboard
| File | Description |
|------|-------------|
| [`frontend/src/App.jsx`](frontend/src/App.jsx) | React Swarm Control Center dashboard. Polls FastAPI server state and provides an interactive interface displaying the PR Board, static MCP checks, Watchdog alerts, Slack-like debate room feed, and manual HITL consent overrides. |
| [`frontend/src/index.css`](frontend/src/index.css) | Custom dark-themed CSS system with glassmorphism panel styling, glowing neon indicators (red for violations, green for compliance), and micro-animations. |

### 🧪 Tests & Mocks
| File | Description |
|------|-------------|
| [`tests/test_swarm.py`](tests/test_swarm.py) | Comprehensive test suite: governance checks (CODEOWNERS matching, consensus rounds, watchdog leaks), real Band.ai connectivity, AIML API partner routing verification, and full swarm orchestration integration test. |
| [`mock_infrastructure/postgres_schema.sql`](mock_infrastructure/postgres_schema.sql) | PostgreSQL checkout database structure (users, products, carts, cart_items, transaction_audit_logs). |
| [`mock_infrastructure/openapi_contract.json`](mock_infrastructure/openapi_contract.json) | OpenAPI spec for `/api/v1/checkout` with required field constraints. |
| [`mock_infrastructure/app_logs.json`](mock_infrastructure/app_logs.json) | Mock application log stream containing memory leak and connection pool exhaustion signatures. |
| [`mock_infrastructure/CODEOWNERS`](mock_infrastructure/CODEOWNERS) | Swarm ownership rules defining high-stakes paths (`/src/auth/`, `/src/billing/`). |
| [`mock_infrastructure/redis_layout.json`](mock_infrastructure/redis_layout.json) | Redis caching layout for inventory concurrency (used by Inventory SME persona context). |

### 📜 Component Demo Scripts
| File | Description |
|------|-------------|
| [`demo_swarm_execution.py`](demo_swarm_execution.py) | Full end-to-end console-based CLI review simulation with `rich` panels. Registers agents on Band.ai, runs adversarial debate rounds, and detects deadlock. |
| [`demo_band_contract.py`](demo_band_contract.py) | Demonstrates Band.ai as the contract focal point: profile retrieval, room listing, room creation, and compliance message broadcast. |
| [`demo_triage_and_hook.py`](demo_triage_and_hook.py) | Demonstrates the pre-commit hook and CODEOWNERS path triage matching across 3 scenarios. |
| [`demo_mcp_verification.py`](demo_mcp_verification.py) | Simulates schema mismatches and OpenAPI contract failures using static MCP checks. |
| [`demo_telemetry_watchdog.py`](demo_telemetry_watchdog.py) | Scans log streams and triggers alert blocks when telemetry anomalies are found. |

### 📋 Configuration & Documentation
| File | Description |
|------|-------------|
| [`codeband.yaml`](codeband.yaml) | Codeband orchestration configuration defining agent frameworks, models, review guidelines, and watchdog settings. |
| [`agent_config.yaml`](agent_config.yaml) | Agent persona credential placeholders (actual keys loaded from `.env`). |
| [`verify_env.py`](verify_env.py) | Pre-flight environment verification script testing connectivity to Anthropic, OpenAI, GitHub, Band.ai, AIML API, and Featherless AI. |
| [`simulate_workflow.py`](simulate_workflow.py) | Offline workflow simulator demonstrating all 5 governance phases without live API calls. |
| [`.env.example`](.env.example) | Template environment configuration with all required keys documented. |
| [`requirements.txt`](requirements.txt) | Python dependency manifest. |

---

## 🛠️ Installation & Setup

### Prerequisites
- **Python 3.12+** with `pip`
- **Node.js 18+** with `npm`

### 1. Clone & Configure
```bash
git clone https://github.com/vjb/WellActually.ai.git
cd WellActually.ai
cp .env.example .env
# Edit .env with your real API keys
```

### 2. Install Dependencies
```powershell
# Python packages
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Frontend packages
cd frontend
npm install
```

### 3. Run Tests
Verify everything is working:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_swarm.py -v
```

### 4. Run Component Demos (offline)
```powershell
.venv\Scripts\python.exe demo_triage_and_hook.py
.venv\Scripts\python.exe demo_mcp_verification.py
.venv\Scripts\python.exe demo_telemetry_watchdog.py
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
   npm run dev
   ```
3. Open your browser and navigate to `http://localhost:5173`.
4. Click **Start Swarm Review** and observe:
   - Zero-trust compliance triage matches billing files and halts execution.
   - Click **Approve Exception** to launch the swarm agents.
   - Watch the chat feed pull remote rooms, rehydrate context, and route reviews dynamically to **Featherless AI** (Auth SME) and **AIML API** (Coder & Cart SME).
   - Observe the adversarial debate as the Coder stubbornly inserts `discount_applied` and Reviewers block it with schema violations.
   - After 3 failed rounds, the **ConsensusTracker** triggers a deadlock halt with HITL escalation.
   - Use the **Override & Approve PR** or **Reject PR** buttons to resolve the deadlock.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     SWARM CONTROL CENTER                         │
│                    (React + Vite Dashboard)                       │
│  ┌────────────┬───────────────┬─────────────┬──────────────────┐ │
│  │ PR Board   │ MCP Checkers  │  Watchdog   │  Debate Feed     │ │
│  │ + Triage   │ Schema+OpenAPI│  Telemetry  │  + HITL Consent  │ │
│  └────────────┴───────────────┴─────────────┴──────────────────┘ │
│                          ↕ REST Polling                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │            FastAPI Backend (src/server.py)                    │ │
│  │  /api/start  /api/status  /api/events  /api/consent          │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                          ↕                                        │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │         Swarm Orchestration (src/swarm.py)                    │ │
│  │  ┌─────────────┐  ┌────────────────────┐  ┌──────────────┐  │ │
│  │  │ Conductor    │  │ Lead Coder Agent   │  │ Reviewer SMEs│  │ │
│  │  │ (AIML API)   │  │ (AIML API gpt-4o)  │  │ Auth: Llama  │  │ │
│  │  │              │  │                    │  │ Cart: gpt-4o │  │ │
│  │  └──────────────┘  └────────────────────┘  └──────────────┘  │ │
│  │                          ↕ Band.ai REST SDK                   │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │ Band.ai Platform: Agents, Rooms, Messages, Mentions,     │ │ │
│  │  │ Context, Events, Memories (local fallback)               │ │ │
│  │  └──────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                          ↕                                        │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │      Governance Engine (src/governance.py)                    │ │
│  │  CODEOWNERS Triage │ ConsensusTracker │ TelemetryScanner     │ │
│  │  Schema Compliance │ OpenAPI Compliance                      │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📜 License

MIT License. Built for the **Band of Agents Hackathon** (June 12–19, 2026).
