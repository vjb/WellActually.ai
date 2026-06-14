# Project: WellActually.ai — Adversarial Code Review Governance Swarm

## Architecture
- **Swarm Orchestration** (`src/swarm.py`): Async agent orchestration mapping to Band.ai REST SDK endpoints.
- **Backend API** (`src/server.py`): FastAPI server powering the real-time web dashboard with REST endpoints.
- **Governance Engine** (`src/governance.py`): Deterministic compliance checks (CODEOWNERS routing, Consensus tracking, MCP schema/OpenAPI verification, and Observability watchdog).
- **Frontend Dashboard** (`frontend/`): React + Vite Swarm Control Center with glassmorphism UI, debate feed, HITL consent controls.
- **Configuration Layer**: `codeband.yaml` and `agent_config.yaml` defining custom agent personas (Conductor, Cart SME, Auth & Fraud SME, Inventory SME).
- **Mock Infrastructure**: Mock databases, queues, and configuration stores (`mock_infrastructure/`).
- **Test Suite** (`tests/test_swarm.py`): Programmatic mocks testing standard workflows, high-stakes blocking, deadlocks, real Band.ai connectivity, and AIML API partner routing.
- **Demo Scripts**: 5 standalone component demos exercising each subsystem independently.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Setup & Verify Env | Perform environment check and verify connectivity | none | DONE |
| 2 | Swarm Config & Mocks | Configure `codeband.yaml` and verify `mock_infrastructure/` | M1 | DONE |
| 3 | Governance Engine | Implement `src/governance.py` | M2 | DONE |
| 4 | Simulation Test Suite | Implement `tests/test_swarm.py` | M3 | DONE |
| 5 | Band.ai Swarm Library | Implement `src/swarm.py` with real SDK calls | M4 | DONE |
| 6 | FastAPI Backend | Implement `src/server.py` with live debate execution | M5 | DONE |
| 7 | Frontend Dashboard | Implement React dashboard with real-time polling | M6 | DONE |
| 8 | Sponsor Integrations | Route Auth SME to Featherless AI, all others to AIML API | M5 | DONE |
| 9 | Security Audit | Sanitize all hardcoded keys, update `.gitignore` | M7 | DONE |
| 10 | Final Verification | Run all tests, demos, and browser UAT | M9 | DONE |
| 11 | Evaluation & Grading v3 | Persona-based grading, verification, and v3 report generation | M10 | DONE |
| 12 | Dynamic PR & Webhook Integration | Verify and implement dynamic GitHub PR endpoints and webhooks | M11 | DONE |



## Interface Contracts
### Governance Engine API (`src/governance.py`)
- `parse_codeowners(content: str) -> dict`: Parses `CODEOWNERS` files. Returns mapping of patterns to metadata/owners.
- `triage_pr(diff_files: list[str], codeowners_rules: dict) -> dict`: Returns triage result dictionary with keys `status` (e.g., "approved", "PENDING_HUMAN_APPROVAL"), `required_approvals` (list of groups), and `is_high_stakes` (bool).
- `class ConsensusTracker`:
  - `__init__(self, max_rounds: int = 2)`
  - `record_round(self, pr_id: str, outcome: str) -> dict`: Records outcome. Returns dict with keys `is_deadlocked` (bool) and `action` (e.g., "continue", "hitl_escalation").
- `class TelemetryScanner`:
  - `__init__(self, log_path: str)`
  - `scan_leaks(self) -> list[dict]`: Parses logs, returns list of detected memory leak logs or alerts.
- `verify_schema_compliance(code_content: str, schema_path: str) -> dict`: Validates code against PostgreSQL schema.
- `verify_openapi_compliance(code_content: str, openapi_path: str) -> dict`: Validates code against OpenAPI contract.
- `verify_rbac_compliance(code_content: str) -> dict`: Validates code against RBAC access policies for sensitive tables. Returns dict with keys `compliant` (bool) and `violations` (list[str]).
- `ConsensusTracker.record_vote(self, pr_id: str, reviewer_name: str, reviewer_role: str, vote: str, round_num: int, domain: str = "")`: Records an individual reviewer's vote (passed/failed) for a given PR round.
- `ConsensusTracker.get_summary(self, pr_id: str) -> dict`: Returns a summary of all recorded votes and rounds for a PR, used for debate telemetry.

### Swarm Orchestration API (`src/swarm.py`)
- `class Agent`: Base LLM-backed persona with `generate_response()`.
- `class CoderAgent(Agent)`: Stubborn coder that inserts `discount_applied`.
- `class ReviewerAgent(Agent)`: SME reviewer with `review_code()` MCP checks.
- `class SwarmSession`: Full lifecycle orchestration with `initialize_session()`, `run_triage()`, `run_debate_round()`, `run_watchdog_scan()`, `cleanup_agents()`.

### Backend API (`src/server.py`)
- `GET /api/status`: Returns swarm state (status, PR, triage, consensus round, MCP checks).
- `GET /api/events`: Returns chronological event feed.
- `POST /api/start`: Launches the simulation as a background task.
- `POST /api/consent`: Submits human approval/rejection for HITL gates.
- `POST /api/reset`: Resets all swarm state back to IDLE. Clears events, triage, code, and consensus data.
- `GET /api/telemetry`: Returns watchdog anomaly scan results.
- `GET /api/mcp`: Returns live MCP schema and OpenAPI compliance checks.

## Code Layout
- `codeband.yaml` — Main Codeband orchestration and guidelines configuration.
- `agent_config.yaml` — Custom agent credential placeholders (real keys in `.env`).
- `requirements.txt` — Python dependency manifest.
- `.env.example` — Template environment configuration.
- `mock_infrastructure/` — Schema, layout, owners, and telemetry logs.
- `src/governance.py` — Core logic for triage, consensus, MCP checks, and observability.
- `src/swarm.py` — Async swarm orchestration with Band.ai SDK integration.
- `src/server.py` — FastAPI backend for the web dashboard.
- `src/githooks/compliance_hook.py` — Git pre-commit compliance hook.
- `frontend/` — React + Vite Swarm Control Center dashboard.
- `tests/test_swarm.py` — Automated scenario test cases.
- `demo_swarm_execution.py` — Full end-to-end CLI demo.
- `demo_band_contract.py` — Band.ai contract focal point demo.
- `demo_triage_and_hook.py` — Compliance triage demo.
- `demo_mcp_verification.py` — MCP bounded context verification demo.
- `demo_telemetry_watchdog.py` — Telemetry watchdog demo.
- `simulate_workflow.py` — Offline workflow simulator.
- `verify_env.py` — Environment verification script.
- `install_hooks.py` — Git hook installer.
