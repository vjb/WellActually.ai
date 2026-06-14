# Enterprise Domain-Driven Swarm: Adversarial Code Review Architecture

## 1. Executive Summary

Standard AI coding agents are limited by a critical flaw: they review code based purely on localized syntax and model intuition, lacking visibility into the external business state, production databases, and corporate compliance rules.

This project introduces **Domain-Driven Adversarial Governance**. Built on top of the `codeband` orchestration pattern and Band.ai, this architecture deploys a swarm of specialized Subject Matter Expert (SME) agents. Instead of generalized code reviews, these agents engage in cross-model adversarial validation. 

### The "Winner Hook": Proof-of-Exploit (PoE) Driven Security Swarms
To prevent **false positives** (a primary pain point of traditional static analysis tools), WellActually.ai introduces **Proof-of-Exploit (PoE) validation**:
1. **Adversarial Red-Team SME**: The **Auth & Fraud SME** acts as an attacker. If a vulnerability is found (like client-side RBAC checks), it demonstrates how the code can be bypassed.
2. **Defensive Blue-Team Coder**: The **Lead Coder** acts as a defender, attempting to revise the code to mitigate the vulnerability.
3. **Verification**: If the Coder's fix succeeds, the Red-Team's exploits fail, and compliance checks pass. If a deadlock is reached, the human operator intervenes and **rejects** the non-compliant PR.

---

## 2. Core Technology Stack

* **Orchestration Layer:** `codeband` (Headless Git worktree isolation, agent routing, and Band.ai synchronization).
* **Network & State Coordination:** Band.ai API & WebSockets.
* **LLM Reasoning Core (Adversarial Multi-Model Pairing):**
  * **AIML API** (`gpt-4o-mini`) — Sponsor Partner. Powers the Lead Coder, Cart SME Reviewer, and Conductor Orchestrator agents.
  * **Featherless AI** (`unsloth/Meta-Llama-3.1-70B-Instruct`) — Sponsor Partner. Powers the Auth & Fraud SME Reviewer agent for specialized security validation.
* **Context Provisioning:** Static Model Context Protocol (MCP) checks via PostgreSQL schema, RBAC policies, and OpenAPI contract. **Reviewer contexts are split by domain**: Auth SME receives schema + RBAC context only; Cart SME receives OpenAPI context only.
* **Governance Engine:** Custom deterministic Python logic (`governance.py`), including regex-based SQL parsing for schema compliance and RBAC compliance verification.
* **Non-Blocking Execution:** Synchronous LLM calls are offloaded using `asyncio.to_thread` to prevent blocking the FastAPI backend event loop.

---

## 3. Architecture Topology & Information Flow

The system operates in a multi-phase, isolated loop to prevent context pollution and ensure rigorous review standards.

1. **Task Ingestion & Triage:** A task or Pull Request is initialized. The **Conductor** evaluates the Git diff. It triggers the `CodeownersTriage` module to determine the risk level of the modified files.
2. **Adversarial Execution:** The native `codeband` **Coders** spin up completely isolated local Git worktrees. The Coder agent receives **stale documentation** listing deprecated columns as valid, causing **emergent non-compliance** rather than scripted failures.
3. **Bounded Context Review (Split MCP):** The code is routed to **domain-differentiated Reviewers**. The **Auth & Fraud SME** receives only schema + RBAC context and validates SQL compliance and role-based access. The **Cart SME** receives only OpenAPI context and validates API contract compliance. Each reviewer operates with isolated, domain-specific prompts — no shared context.
4. **Governance Oversight & Consensus**: As the Coder and Reviewer debate the implementation, the custom `ConsensusTracker` monitors the Band room with **per-reviewer vote tracking** via `record_vote()` and `get_summary()`. If they fail to reach an agreement within the designated 2-round threshold, the automated flow is halted.
5. **Observability Injection**: Simultaneously, the `ObservabilityAgent` daemon scans live system telemetry, injecting warnings directly into the activity feed if the modified endpoints correspond with known historical regressions (e.g., query loops on the billing service).
6. **Human-in-the-Loop Rejection**: The human operator reviews the deadlocked debate and clicks **Reject PR**, terminating the review and logging: `❌ Human Operator agreed with SME and REJECTED the PR.`

---

## 4. Domain-Driven Agent Personas

The generic `codeband` worker pools are specialized into distinct enterprise domains using `agent_config.yaml`.

| Agent Identity | LLM Provider / Model | Core Responsibility |
| --- | --- | --- |
| **Conductor** | AIML API (`gpt-4o-mini`) | The Swarm Orchestrator. Evaluates PR metadata, triggers routing, and enforces the `CODEOWNERS` policy. |
| **Lead Coder** | AIML API (`gpt-4o-mini`) | The Blue Team. Writes spending report proposals and responds to reviewer feedback with revisions. |
| **Auth & Fraud SME** | Featherless AI (`Llama-3.1-70B`) + `PostgreSQL MCP` + `RBAC MCP` | The Red Team. Receives **split MCP context** (schema + RBAC only). Verifies database schema integrity and forces standard RBAC middleware, catching bypass attempts. |
| **Cart SME** | AIML API (`gpt-4o-mini`) + `OpenAPI MCP` | The Checkout Guard. Receives **split MCP context** (OpenAPI only). Validates payload schemas for the Cart microservice. |

---

## 5. Deterministic Governance Engine Specification

To transition from a "weekend hack" to an enterprise-ready product, the prompt-based decision-making is heavily augmented by `governance.py`—a deterministic Python rules engine.

### A. CodeownersTriage (Compliance Policy)
* **Logic:** Parses a mock `mock_infrastructure/CODEOWNERS` file. If the PR diff includes paths assigned to restricted teams (e.g., `/src/auth/` or `/src/billing/`), the engine overrides the agents' approval.
* **Action:** Forces a mandatory triage escalation, suspending the room until explicit administrative approval is provided.

### B. ConsensusTracker (Deadlock Resolution & Vote Tracking)
* **Logic:** Tracks the adversarial iterations between a Coder and Reviewers with **per-reviewer vote tracking**. Each reviewer's vote (approve/reject) is recorded individually via `record_vote(reviewer, decision)`. The tracker generates structured summaries via `get_summary()`.
* **Action:** If the Coder submits a fix and the Reviewers reject it twice consecutively, the engine identifies a logic deadlock. It halts the loop, preventing token waste, and issues an alert for Human-in-the-Loop intervention.

### C. Schema Compliance (SQL Parsing Engine)
* **Logic:** `verify_schema_compliance` **parses both INSERT and SELECT statements via regex**, extracts column names from the SQL, and diffs them against the actual `postgres_schema.sql` file.
* **Action:** Any non-existent column produces a structured violation report injected into the Auth SME Reviewer's context.

### D. RBAC Compliance (Access Control Verification)
* **Logic:** `verify_rbac_compliance` scans code for direct access to protected fields without RBAC role guards.
* **Action:** Produces a structured violation report for the Auth SME Reviewer if client-side role checks are used instead of required middleware.

---

## 6. Testing & Verification Blueprint

To guarantee flawless hackathon demonstrations and robust CI/CD integration, the system utilizes a fast, programmatic mocking strategy via `pytest` (`tests/test_swarm.py`). The suite has grown to **36 tests** validating governance logic, compliance engines, and reviewer differentiation entirely offline:

1. **`test_standard_pr_flow`:** Validates the happy path where a low-stakes file passes adversarial review and merges.
2. **`test_high_stakes_pr_escalation`:** Verifies that a diff touching restricted paths successfully triggers the triage intercept and halts execution.
3. **`test_deadlock_consensus_escalation`:** Simulates a 2-turn rejection loop, verifying that the `ConsensusTracker` correctly pauses the room.
4. **`test_observability_leak_detection`:** Asserts that the telemetry daemon successfully parses log anomalies.
5. **SQL Parsing Tests:** Validate that `verify_schema_compliance` correctly parses INSERT and SELECT statements, extracts column names, and catches non-existent columns.
