# WellActually.ai 🧠🤖
### Domain-Driven Adversarial Code Review Swarm Center
*A multi-agent compliance & governance platform built on **Band.ai** and powered by **Featherless AI** & **AIML API**.*

> **🏆 Track 2: Multi-Agent Software Development** — Cross-model code review with adversarial consensus, bounded-context validation, and human-in-the-loop governance.

---

## 🎬 Demo Video

> *Coming soon — demo video will be added before submission.*

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

### 4. **Codeband** (Architectural Reference)
WellActually.ai is built on the same **Band.ai REST SDK** (`thenvoi-rest`) that powers [Codeband](https://github.com/thenvoi/codeband). We use Codeband as the **reference implementation** for adversarial multi-model review workflows, extending the pattern with:
- **Domain-Driven Governance** — a deterministic `governance.py` engine that enforces CODEOWNERS policies, consensus tracking, and MCP bounded-context validation on top of the LLM debate.
- **Cross-Provider Adversarial Pairing** — instead of Claude vs Codex, we pair **Featherless AI** (Llama-3.1-70B) against **AIML API** (GPT-4o-mini), maximizing review diversity across model architectures and sponsor integrations.
- **Human-in-the-Loop Escalation** — deterministic deadlock detection with async blocking consent gates, expanding Codeband's risk-aware merging concept into full HITL governance.
- **Real-Time Web Dashboard** — a React Swarm Control Center providing live visibility into the debate, compliance checks, and telemetry anomalies.

The included `codeband.yaml` defines our agent topology following Codeband's configuration schema (Conductor, Coders, Reviewers, Watchdog, Mergemaster), demonstrating compatibility with the Codeband orchestration model.

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

### 📸 Dashboard Screenshots

| Idle State | Pending Human Approval | Live Debate |
|:---:|:---:|:---:|
| ![Idle](docs/screenshots/01_idle_state.png) | ![Pending](docs/screenshots/02_pending_approval.png) | ![Running](docs/screenshots/03_running_debate.png) |

| Deadlock & HITL | Code Tab (Syntax Highlighted) |
|:---:|:---:|
| ![Halted](docs/screenshots/04_halted_deadlock.png) | ![Code](docs/screenshots/05_code_tab_highlighted.png) |

---

## 🔬 Demo Scope: What's Real vs. Simulated

This is a hackathon prototype. The **architecture and agent orchestration are production-grade**; the **input data is simulated** to demonstrate the governance workflow in a controlled environment.

### ✅ Real (Live Infrastructure)
| Component | Detail |
|-----------|--------|
| **Band.ai Multi-Agent Platform** | Real agent registration, real chat rooms, real message passing, real context rehydration — all via Band.ai REST SDK. |
| **LLM Adversarial Debate** | Live API calls to **Featherless AI** (Llama-3.1-70B) and **AIML API** (GPT-4o-mini). Reviewers genuinely analyze code and produce original responses every run. |
| **Deadlock Detection** | The `ConsensusTracker` in `governance.py` counts rounds and triggers the halt — the Coder genuinely refuses to comply and Reviewers genuinely reject. |
| **Human-in-the-Loop Gates** | Real state machine with async blocking — the swarm literally pauses until a human clicks Approve or Reject. |
| **Memory Persistence** | Schema violation memories are stored and rehydrated across rounds (local JSONL fallback for Band.ai Enterprise Memory API). |
| **Pre-Commit Git Hook** | Actually runs on `git commit` and blocks commits touching high-stakes paths. |

### 🎭 Simulated (Mock Data for Demo)

The system uses a **two-layer architecture**: deterministic governance gates (Layer 1) feed structured violation reports into LLM agents (Layer 2) who perform adversarial reasoning. The mock data below is for Layer 1 inputs only — the LLM debate itself is fully live and non-deterministic.

| Component | What's Mocked (Layer 1) | What the LLMs Add (Layer 2) | Production Path |
|-----------|------------------------|----------------------------|------------------|
| **Pull Request** | Hardcoded to PR-104 touching `src/cart/` and `src/billing/`. | N/A — triage is deterministic. | GitHub Webhooks for real PR payloads. |
| **Database Schema Check** | The governance engine pattern-matches code against a static `postgres_schema.sql` and produces a structured violation report (e.g., `"Column 'discount_applied' does not exist in table 'cart_items'"`). | The violation report is **injected as context** into the Reviewer LLM prompt. The Reviewer then writes a *detailed code review* explaining the security/data integrity implications. The Coder LLM receives this review and produces a *novel workaround* (try/except, local dict, ALTER TABLE) — each round is different. This adversarial reasoning is why LLMs are essential. | Live Postgres `information_schema` query or a real MCP server. |
| **OpenAPI Contract Check** | Validates code against a static `openapi_contract.json` file. | Same two-layer flow: structured violations feed LLM reasoning. | Live OpenAPI spec from service registry. |
| **Telemetry Watchdog** | Reads anomalies from a static `app_logs.json` file. | Surfaces anomalies in the dashboard for human context during HITL decisions. | Datadog/Prometheus/OpenTelemetry streams. |
| **Coder Stubbornness** | The Coder's system prompt steers it to always include `discount_applied` in its initial SQL. | But each revision is *genuinely different* — the LLM invents creative workarounds (wrapping in try/except, adding fallback dicts, proposing ALTER statements). The Reviewers must analyze each new strategy independently. This emergent adversarial behavior cannot be scripted. | In production, the Coder receives real PR diffs. |

> **Why this matters:** The simulated inputs let us demonstrate the *complete governance workflow* (triage → consent → debate → deadlock → HITL) reliably in a 7-day hackathon. The architecture itself — agent orchestration, adversarial consensus, multi-model routing, and human escalation — is designed to plug into real infrastructure with minimal changes.

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

## 👥 Team

Built by **VJ Beltrani** for the [Band of Agents Hackathon](https://lablab.ai/event/band-of-agents-hackathon) (June 12–19, 2026).

---

## 📜 License

MIT License. Built for the **Band of Agents Hackathon** (June 12–19, 2026).
