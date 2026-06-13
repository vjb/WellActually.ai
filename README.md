# WellActually.ai 🧠🤖
### Domain-Driven Adversarial Code Review Swarm Center
*A multi-agent compliance & governance platform built on **Band.ai** and powered by **Featherless AI** & **AIML API**.*

> **🏆 Track 2: Multi-Agent Software Development** — Cross-model code review with adversarial consensus, bounded-context validation, and human-in-the-loop governance.

---

## 🎬 Demo Video

> *Coming soon — demo video will be added before submission.*

---

## 🚀 Overview

**WellActually.ai** is an enterprise-grade adversarial code review and compliance swarm. It enforces **Zero-Trust compliance** policies by dynamically triaging code modifications, launching specialized Subject Matter Expert (SME) agents to validate changes against bounded contexts (database schemas & API specifications), and monitoring live runtime logs via an observability watchdog.

### The "Winner Hook": Proof-of-Exploit (PoE) Driven Security Swarms
Standard static compliance tools are plagued by **false positives**, leading to constant arguments between developers and security teams. WellActually.ai shifts this paradigm by executing **Proof-of-Exploit (PoE)** validation during the pull request phase:
1. **Adversarial Red-Team SME**: The **Auth & Fraud SME** acts as an attacker. If a security vulnerability is identified (like client-side RBAC checks), it demonstrates how the code can be bypassed.
2. **Defensive Blue-Team Coder**: The **Lead Coder** acts as a defender, attempting to revise the code to mitigate the vulnerability.
3. **Verification**: If the Coder's fix succeeds, the Red-Team's exploits fail, and the code compliance checks pass. If a deadlock is reached, the system halts and escalates to a human operator, who reviews the adversarial log and **rejects** the non-compliant PR.

---

## ── The Demo Scenario: RBAC Bypass ──

A junior developer submits `src/billing/spending_report.py` to retrieve user spending limits. They write it using **stale documentation** that has two lies:
1. Lists a `discount_tier` column that was **removed in a schema migration**.
2. Says "no auth middleware required for service reads" — a policy that was **revoked** when billing data was reclassified as sensitive financial PII.

### Round-by-Round Narrative Arc

* **Initial Triage**: The Zero-Trust compliance scanner matches billing paths and halts the automatic merge pipeline, requiring human operator manual consent to launch the swarm review.
* **JIRA Context Injection**: The system fetches ground-truth ticket requirements:
  `[JIRA INTEGRATION] Fetched context for Ticket SEC-842: "Implement spending report fetcher. MUST use standard rbac.check_access() middleware."`
* **Round 1 (Double Violation)**:
  * The Coder queries both `spending_limit_usd` and `discount_tier` with direct SQL and no role verification.
  * **MCP checks** catch both: PostgreSQL Schema detects a missing column (`discount_tier`); RBAC checks catch unguarded financial access.
  * **Auth & Fraud SME** (Meta-Llama-3.1-70B on **Featherless AI**) rejects the code citing both schema and RBAC policy failures.
  * **Cart SME** (GPT-4o-mini on **AIML API**) passes the code since it does not touch the Cart domain contract.
* **Round 2 (Half-Fix / Bypassed Security)**:
  * The Coder fixes the column name (removes `discount_tier`) but attempts to bypass the RBAC requirements by adding a naive client-side `if user_role not in ['admin', 'finance']` check instead of the standard decorators/middleware, violating the JIRA acceptance criteria.
  * **MCP checks** show the schema is now compliant (✅) but the RBAC check fails (❌) because client-side role guards are insufficient for production financial access.
  * **Auth & Fraud SME** detects the bypass attempt and rejects the code again.
  * **Cart SME** passes.
* **Deadlock Escalation**:
  * Having exceeded the round limit with conflicting votes (Auth SME rejecting twice, Cart SME passing twice), the **ConsensusTracker** declares a deadlock.
  * The system halts the review, publishes a halt event to the Band room, and prompts the human operator.
  * The human operator reviews the debate, agrees with the SME, and **rejects the PR**, enforcing secure coding practices.

---

## ── Live Dynamic Repository & PR Flow (v6) ──

WellActually.ai is fully generalized to run reviews on **any** public GitHub pull request. It analyzes code modifications in real time, generates custom agent personas on the fly, executes dynamic MCP schema/contract validations, and posts results back to GitHub:

* **Dynamic Repository & PR Loading**: Developers can type any repository path (e.g. `vjb/WellActually.ai`) and select from available open pull requests. The system fetches metadata, list of touched files, and raw code diffs dynamically.
* **On-the-fly Agent Identity Generation**: Filenames and extensions modified in the PR are scanned to dynamically invent relevant reviewer agent roles and domains (e.g. `Environment Configuration Security SME` for `.env.example`, `API Contract & Integration SME` for JSON contracts, `Database Schema Compliance SME` for SQL changes). 
* **Dynamic MCP Bounded-Context Targets**: The Postgres tables, REST endpoints, and RBAC column targets are dynamically extracted from the PR code changes instead of falling back to hardcoded path strings.
* **Automated Webhook Integration**: Exposes `/api/webhooks/github` to trigger compliance triages automatically on `pull_request` events, with a webhook simulator interface built directly into the dashboard.
* **VCS Scorecard Commenting**: Upon completing the review, the swarm automatically posts a markdown audit scorecard directly back to the GitHub PR.

---

## 🤝 Platform & Partner Stack Integrations

### 1. **Band.ai** (Core Agent Collaboration)
Our swarm orchestrates real-time communication directly over the **Band.ai REST SDK** platform:
- **Identity & Registrations**: Registers Conductor, Coder, and Reviewer agents on the platform.
- **Chat Rooms & Participants**: Dynamically instantiates review rooms and adds agent participants.
- **Messages & Mentions**: Agents exchange context and code proposals using targeted `@mentions` (e.g., Coder mentioning Conductor, Reviewer mentioning Coder).
- **Context Rehydration**: Reviewers query the Chat Context endpoint before running evaluations to load the latest history.
- **Events**: Publishes custom chat error events to notify participants of deadlocks.
- **Agent Reuse Mechanism**: Automatically detects the platform's 10-agent limit and reuses pre-registered agent credentials (loaded from environment variables) to prevent registration failures.
- **Memories (Local Fallback)**: Automatically falls back to local JSON persistence (`mock_infrastructure/local_memories.json`) upon detecting plan limitations on Free/Pro tiers, ensuring zero-crash memory rehydration.

### 2. **Featherless AI** (Hackathon Sponsor Partner)
To leverage specialized open-source models at scale, we route the **First Reviewer Agent** to the `unsloth/Meta-Llama-3.1-70B-Instruct` model hosted on **Featherless AI's** serverless endpoint (`https://api.featherless.ai/v1`). The model's role and domain are dynamically generated based on files modified (e.g. `Environment Configuration Security SME`). It performs strict syntax verification, RBAC checks, and schema validation. The Featherless AI integration ensures our adversarial pairing uses genuinely different model architectures (Llama 3.1 vs GPT-4o) to maximize review diversity.

### 3. **AIML API** (Hackathon Sponsor Partner)
All other agents in the swarm (the Conductor Orchestrator, the Lead Coder, and the **Second Reviewer Agent**) are routed via the **AIML API** gateway (`https://api.aimlapi.com/v1`) using the `gpt-4o-mini` model. The Second Reviewer Agent's identity is dynamically generated based on touched files (e.g. `API Contract & Integration SME` for JSON files). By redirecting `OPENAI_BASE_URL` to the AIML API endpoint, we achieve seamless integration with the sponsor's infrastructure while maintaining standard OpenAI client compatibility.

### 4. **GitHub** (Scorecard Workflow Integration)
WellActually.ai connects directly to the developer's VCS flow to publish audit scorecards:
- **PR Commenting**: Extracts the pull request number dynamically from the swarm state and posts a detailed markdown audit scorecard.
- **Resilient Fallback**: If the pull request number does not exist on GitHub, the system catches the HTTP 404 error and automatically instantiates a new GitHub Issue instead to log the audit report.
- **Developer Observation**: Developers can track exact compliance results (PostgreSQL Schema violations, OpenAPI Contract failures, Middleware RBAC warnings, and log stream anomalies) right inside their code repository.

### 5. **Codeband** (Architectural Reference)
WellActually.ai is built on the same **Band.ai REST SDK** (`thenvoi-rest`) that powers [Codeband](https://github.com/thenvoi/codeband). We use Codeband as the reference implementation, extending the pattern with:
- **Domain-Driven Governance** — a deterministic `governance.py` engine that enforces CODEOWNERS policies, consensus tracking, and MCP bounded-context validation on top of the LLM debate.
- **Cross-Provider Adversarial Pairing** — pairing **Featherless AI** (Llama-3.1-70B) against **AIML API** (gpt-4o-mini).
- **Human-in-the-Loop Escalation** — deterministic deadlock detection with async blocking consent gates, expanding Codeband's risk-aware merging concept into full HITL governance.
- **Real-Time Web Dashboard** — a React Swarm Control Center providing live visibility into the debate, compliance checks, and telemetry anomalies.

---

## 📂 Repository File Directory Structure

Every file in the repository plays a precise role in the Domain-Driven Governance engine:

### ⚙️ Core Swarm & Backend
| File | Description |
|------|-------------|
| [`src/swarm.py`](src/swarm.py) | Async Swarm Orchestration library mapping Python Agent classes to Band.ai REST SDK endpoints. Offloads synchronous LLM network calls to a threadpool via `asyncio.to_thread` to prevent blocking the event loop. |
| [`src/server.py`](src/server.py) | FastAPI server exposing REST endpoints (`/api/status`, `/api/events`, `/api/start`, `/api/consent`, `/api/telemetry`, `/api/mcp`) to manage swarm state, events, manual HITL overrides, and logs. |
| [`src/governance.py`](src/governance.py) | The deterministic compliance and validation engine — `parse_codeowners`, `triage_pr`, `ConsensusTracker` (with per-reviewer `record_vote()` / `get_summary()`), `verify_schema_compliance` (regex-based SQL parsing for both INSERT and SELECT), `verify_rbac_compliance`, `verify_openapi_compliance`, and `TelemetryScanner`. |
| [`src/githooks/compliance_hook.py`](src/githooks/compliance_hook.py) | Git pre-commit hook enforcing compliance triage locally. Blocks commits touching high-stakes paths. |
| [`install_hooks.py`](install_hooks.py) | Automates installation of the git pre-commit compliance hook. |

### 💻 Frontend Web Dashboard
| File | Description |
|------|-------------|
| [`frontend/src/App.jsx`](frontend/src/App.jsx) | React Swarm Control Center dashboard. Includes a clean layout, a Slack-like debate room feed, manual HITL consent overrides, and a **post-debate analytics summary card** displaying dynamic round progress (`Round X of 2`). |
| [`frontend/src/index.css`](frontend/src/index.css) | Custom dark-themed CSS system with glassmorphism panel styling, glowing neon indicators (red for violations, green for compliance), and micro-animations. |

### 🧪 Tests & Mocks
| File | Description |
|------|-------------|
| [`tests/test_swarm.py`](tests/test_swarm.py) | Comprehensive test suite (**36 tests**): governance checks (CODEOWNERS matching, consensus rounds, watchdog leaks), SQL-parsing schema compliance, RBAC compliance, per-reviewer vote tracking, scenario selection, split reviewer contexts, post-debate summary generation, real Band.ai connectivity, AIML API partner routing verification, and full swarm orchestration integration test. |
| [`mock_infrastructure/postgres_schema.sql`](mock_infrastructure/postgres_schema.sql) | PostgreSQL database structure (users, products, carts, cart_items, transaction_audit_logs, billing_profiles). |
| [`mock_infrastructure/openapi_contract.json`](mock_infrastructure/openapi_contract.json) | OpenAPI spec for `/api/v1/checkout` and `/api/v1/billing/spending` endpoints. |
| [`mock_infrastructure/app_logs.json`](mock_infrastructure/app_logs.json) | Mock application log stream containing only relevant `billing-service` query rate anomalies to avoid dashboard noise. |
| [`mock_infrastructure/CODEOWNERS`](mock_infrastructure/CODEOWNERS) | Swarm ownership rules defining high-stakes paths (`/src/auth/`, `/src/billing/`). |

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
4. **Load a Repository Pull Request**:
   - In the **Repository** field, enter `vjb/WellActually.ai` (or any other repo).
   - In the **Pull Request** dropdown, select an open PR (e.g. PR #1).
   - Notice the **Webhook Simulator** repository and PR number automatically sync.
5. **Run the Swarm Review**:
   - Click **Start Swarm Review**.
   - If the PR touches high-stakes files (like `.env.example` or `schema.sql`), the Zero-Trust compliance scanner halts the pipeline, prompting for human operator consent.
   - Click **Approve Exception** to authorize agent launch.
   - Watch the **Agent Topology** graph dynamically render newly created reviewer roles based on touched files (e.g. `Environment Configuration Security SME` 🛡️).
   - Observe the live debate round feed as agents use Featherless AI and AIML API to review the actual PR diff shown in the **Proposed Implementation** tab.
   - Once consensus is reached or a deadlock escalates, see the post-debate summary card.
   - Check the GitHub repository PR page: the swarm will have posted a compiled markdown **Audit Scorecard** directly as a comment on the PR!

6. **Simulate Webhooks**:
   - In the Webhook Simulator panel, adjust repository/PR details if desired and click **Simulate Webhook Trigger** to trigger a background compliance run.

---

## 🗄️ PostgreSQL Live DB Checks (v5)

WellActually.ai supports a dual-mode database compliance check. 
By default, it parses static schemas from `mock_infrastructure/postgres_schema.sql`. To run live schema checks against a running database:

1. **Spin up a local PostgreSQL container**:
   ```powershell
   docker run --name wellactually-postgres -e POSTGRES_DB=wellactually -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres
   ```
2. **Load mock schema DDL**: Load `mock_infrastructure/postgres_schema.sql` into the container.
3. **Configure your `.env` settings**:
   ```env
   USE_REAL_DB=true
   DATABASE_URL="postgresql://postgres:postgres@localhost:5432/wellactually"
   ```
   *Note: Spawning the postgres MCP server requires Node.js 18+.*

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
│                          ↕ REST Polling (Non-Blocking)            │
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
│  │  CODEOWNERS Triage │ ConsensusTracker (vote tracking)        │ │
│  │  Schema Compliance │ RBAC Compliance │ OpenAPI Compliance    │ │
│  │  TelemetryScanner  │ Scenario Engine                         │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 👥 Team

Built by **VJ Beltrani** for the [Band of Agents Hackathon](https://lablab.ai/event/band-of-agents-hackathon) (June 12–19, 2026).

---

## 📜 License

MIT License. Built for the **Band of Agents Hackathon** (June 12–19, 2026).
