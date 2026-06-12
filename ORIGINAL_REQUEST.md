# Original User Request

## Initial Request — 2026-06-12T12:07:28-04:00

Build an enterprise-grade, multi-agent autonomous code review swarm using `codeband` that implements Domain-Driven Adversarial Governance with specialized subject-matter expert (SME) personas, local bounded context (MCP) verification, and human-in-the-loop (HITL) escalation. The system is verified by a `pytest` test suite simulating standard PR, high-stakes PR, and consensus deadlock scenarios.

Working directory: `c:\Users\vjbel\hacks\BOA`
Integrity mode: demo

## Requirements

### R1. Swarm Persona Configuration
- Define and configure custom prompts/personas for `Conductor`, `Cart SME` (Claude Reviewer), `Auth & Fraud SME` (Codex Reviewer), and `Inventory SME` (Codex Reviewer) within Codeband configuration structures (`codeband.yaml` and `agent_config.yaml`).
- Establish `mock_infrastructure/` containing postgres_schema.sql, redis_layout.json, app_logs.json, and CODEOWNERS.

### R2. Deterministic Governance Engine (`src/governance.py`)
- **CODEOWNERS Triage**: A parser that reads `mock_infrastructure/CODEOWNERS` and matches files modified in a PR diff. If a path under `/src/auth/` or `/src/billing/` is modified, flags the PR as "high-stakes" and routes it for mandatory human approval.
- **Consensus Tracker**: A state tracker that counts review rounds. If a Coder and Reviewer fail to agree on a PR (feedback iteration count exceeds 2 rounds), flags the session as "deadlocked" and triggers a Human-in-the-Loop escalation.
- **Observability Watchdog**: A telemetry parser that scans `mock_infrastructure/app_logs.json` for warning patterns (specifically matching the memory leak signature) and logs an alert.

### R3. Automated Simulation Test Suite (`tests/test_swarm.py`)
- Implement `pytest` test cases utilizing programmatic mocks (intercepting client/websocket connections) to simulate the execution pathways without calling external live endpoints.
- **Scenario 1: Standard PR**: Modifies a low-stakes file (e.g. `/src/cart/`), passes review, and automatically routes to Mergemaster.
- **Scenario 2: High-Stakes PR**: Modifies a file in `/src/auth/`, triggers the CODEOWNERS rule, pauses execution, and requests human approval.
- **Scenario 3: Consensus Deadlock**: Simulates Coder pushing changes and Reviewer failing them repeatedly. Triggers a deadlock escalation on round 3.
- **Scenario 4: Observability Alert**: Verifies the telemetry scanner finds and flags the memory leak signature.

## Acceptance Criteria

### Execution & Verification
- [ ] `cb doctor` runs successfully and reports clean configurations.
- [ ] Running `pytest tests/test_swarm.py` runs and passes all 4 simulated scenarios cleanly.
- [ ] The governance engine (`src/governance.py`) implements the checks programmatically without relying purely on LLM prompts.
- [ ] All code runs cleanly on Windows.
