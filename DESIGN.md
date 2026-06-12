# Enterprise Domain-Driven Swarm: Adversarial Code Review Architecture

## 1. Executive Summary

Standard AI coding agents are limited by a critical flaw: they review code based purely on localized syntax and model intuition, lacking visibility into the external business state, production databases, and corporate compliance rules.

This project introduces **Domain-Driven Adversarial Governance**. Built on top of the `codeband` orchestration framework and Band.ai, this architecture deploys a swarm of specialized Subject Matter Expert (SME) agents. Instead of generalized code reviews, these agents engage in cross-model adversarial validation. By utilizing the **Model Context Protocol (MCP)**, the agents possess "Bounded Context"—the ability to securely query external database schemas, caching layouts, and API contracts to validate PRs against real-world business logic.

Furthermore, the swarm is governed by a deterministic, code-backed engine that enforces strict enterprise compliance (via `CODEOWNERS`) and orchestrates Human-in-the-Loop (HITL) escalations during deadlocks or high-stakes modifications.

## 2. Core Technology Stack

* **Orchestration Layer:** `codeband` (Headless Git worktree isolation, agent routing, and Band.ai synchronization).
* **Network & State Coordination:** Band.ai API & WebSockets.
* **LLM Reasoning Core (Adversarial Multi-Model Pairing):**
  * **AIML API** (`gpt-4o-mini`) — Sponsor Partner. Powers the Lead Coder, Cart SME Reviewer, and Conductor Orchestrator agents.
  * **Featherless AI** (`unsloth/Meta-Llama-3.1-70B-Instruct`) — Sponsor Partner. Powers the Auth & Fraud SME Reviewer agent for specialized security validation.
* **Context Provisioning:** Static Model Context Protocol (MCP) checks via PostgreSQL schema and OpenAPI contract.
* **Governance Engine:** Custom deterministic Python logic (`governance.py`).

---

## 3. Architecture Topology & Information Flow

The system operates in a multi-phase, isolated loop to prevent context pollution and ensure rigorous review standards.

1. **Task Ingestion & Triage:** A task or Pull Request is initialized. The **Conductor** evaluates the Git diff and original Jira requirements. It triggers the `CodeownersTriage` module to determine the risk level of the modified files.
2. **Adversarial Execution:** The native `codeband` **Coders** spin up completely isolated local Git worktrees. A Claude Coder implements the feature.
3. **Bounded Context Review:** The code is routed to the opposite-framework **Reviewers** (e.g., Codex/AIML). These reviewers are assigned specific enterprise personas. They utilize local MCP servers to pull bounded context (e.g., verifying a schema change via the PostgreSQL MCP).
4. **Governance Oversight:** As the Coder and Reviewer debate the implementation, the custom `ConsensusTracker` monitors the Band room. If they fail to reach an agreement within a designated threshold, the automated flow is halted.
5. **Observability Injection:** Simultaneously, the `ObservabilityAgent` daemon scans live system telemetry, injecting warnings directly into the `codeband` activity feed if the modified endpoints correspond with known historical regressions.

---

## 4. Domain-Driven Agent Personas

The generic `codeband` worker pools are specialized into distinct enterprise domains using `agent_config.yaml`.

| Agent Identity | Framework / Tooling | Core Responsibility |
| --- | --- | --- |
| **Conductor** | Claude | The Swarm Orchestrator. Evaluates PR metadata, triggers routing, and enforces the `CODEOWNERS` policy. |
| **Auth & Fraud SME** | Codex (AI/ML API) + `PostgreSQL MCP` + `OpenAPI MCP` | The Security Guard. Verifies that incoming PRs do not accidentally expose sensitive endpoints, bypass user roles, or violate financial SQL constraints. |
| **Cart SME** | Claude + `OpenAPI MCP` | The Checkout Guard. Ensures changes do not break state machines, pricing calculations, or payload schemas for the Cart microservice. |
| **Inventory SME** | Codex (AI/ML API) + `Redis MCP` | The Concurrency Guard. Inspects caching layouts and distributed locks to prevent data racing and stock overselling in fulfillment queues. |
| **Mergemaster** | Claude | Final integration check ensuring regression tests pass before approving the final automated branch merge. |

---

## 5. Deterministic Governance Engine Specification

To transition from a "weekend hack" to an enterprise-ready product, the prompt-based decision-making is heavily augmented by `governance.py`—a deterministic Python rules engine.

### A. CodeownersTriage (Compliance Policy)

* **Logic:** Parses a mock `mock_infrastructure/CODEOWNERS` file. If the PR diff includes paths assigned to restricted teams (e.g., `/src/auth/` or `/src/billing/`), the engine overrides the agents' approval.
* **Action:** Forces a mandatory `@@human` escalation, suspending the `codeband` room until explicit administrative approval is provided.

### B. ConsensusTracker (Deadlock Resolution)

* **Logic:** Tracks the adversarial iterations between a Coder and a Reviewer.
* **Action:** If the Coder submits a fix and the Reviewer rejects it three times consecutively, the engine identifies a logic deadlock. It halts the loop, preventing token waste, and issues an alert for Human-in-the-Loop intervention.

### C. ObservabilityAgent (Telemetry Daemon)

* **Logic:** An in-process daemon that parses `mock_infrastructure/app_logs.json`.
* **Action:** Looks for critical runtime exceptions (e.g., memory leaks, database connection drops) tied to the actively modified service, broadcasting actionable intelligence into the active Band chat room.

### D. Local Memory Fallback Database

* **Logic:** The Band.ai platform limits the Memory API (storing/retrieving agent semantic memories) strictly to Enterprise tier accounts, throwing `403 Forbidden` exceptions on other tiers. To resolve this limitation, we implemented a robust programmatic fallback that intercepts `403` exceptions or activates directly when `BAND_MEMORY_MODE=local` is set in the environment.
* **Action:** Saves agent semantic memories locally to a structured JSON file at `mock_infrastructure/local_memories.json` and loads existing memories to feed into agent system prompts during debate context rehydration, bypassing platform limitations and ensuring zero-crashes.

---

## 6. Testing & Verification Blueprint

To guarantee flawless hackathon demonstrations and robust CI/CD integration, the system utilizes a fast, programmatic mocking strategy via `pytest` (`tests/test_swarm.py`). The suite validates the governance logic entirely offline:

1. **`test_standard_pr_flow`:** Validates the happy path where a low-stakes file (e.g., `/src/cart/ui.js`) passes adversarial review and merges seamlessly.
2. **`test_high_stakes_pr_escalation`:** Verifies that a diff touching `/src/auth/jwt.py` successfully triggers the `CodeownersTriage` intercept and halts execution.
3. **`test_deadlock_consensus_escalation`:** Simulates a mocked 3-turn rejection loop between the Cart SME and the Codex Coder, verifying that the `ConsensusTracker` correctly pauses the room.
4. **`test_observability_leak_detection`:** Asserts that the daemon successfully parses a simulated JSON memory leak and formats the correct Band broadcast payload.

---

## 7. Strategic Hackathon Differentiators

* **The Partner Track Advantage:** By overriding `OPENAI_BASE_URL`, the Codex CLI framework is seamlessly redirected to the **AI/ML API** platform, qualifying the project for the partner prize track while maintaining adversarial integrity.
* **Beyond "Vibe Coding":** This is not a swarm arbitrarily modifying code. It enforces rigid corporate boundaries (`CODEOWNERS`) and relies on real system state (MCP database queries) rather than LLM intuition.
* **The Integration of Frameworks:** Brilliantly combines `codeband` for git worktree isolation, Band.ai for protocol-level multi-agent routing, and MCP for Bounded Context execution, representing the bleeding edge of agentic software engineering.
