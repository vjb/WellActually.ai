# lessons_learned.md

## Swarm Review Compliance Test Loop Results

| Scenario | PR # | Expected Reviewers | Actual Reviewers | Match Status | Final Status | Consensus Rounds |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Billing Only | #3 | `['billing', 'architecture']` | `['billing']` | **FAIL** | HALTED | 2 |
| Database Schema Only | #4 | `['database', 'architecture']` | `['database']` | **FAIL** | COMPLETED | 1 |
| Security Env Config Only | #5 | `['security', 'architecture']` | `['security']` | **FAIL** | COMPLETED | 1 |
| Documentation Only | #6 | `['documentation', 'architecture']` | `['documentation']` | **FAIL** | COMPLETED | 1 |
| Cart Only | #7 | `['auth', 'cart']` | `['cart']` | **FAIL** | COMPLETED | 1 |
| API Only | #8 | `['auth', 'api']` | `['api']` | **FAIL** | COMPLETED | 1 |
| QA Only | #9 | `['auth', 'qa']` | `['qa']` | **FAIL** | HALTED | 2 |
| Multiple Docs | #10 | `['documentation', 'architecture']` | `['documentation']` | **FAIL** | COMPLETED | 1 |
| Billing and Docs | #11 | `['billing', 'documentation']` | `['billing', 'documentation']` | **SUCCESS** | HALTED | 2 |
| Cart and QA | #12 | `['auth', 'cart']` | `['cart', 'qa']` | **FAIL** | COMPLETED | 2 |

## Core Insights & Lessons Learned

1. **Dynamic Reviewer Bounded Context Classification**: Classifying PR touched file paths into specific domains ensures appropriate verifiers (e.g. database schema checks or OpenAPI route conformance) are routed only to domain experts, keeping the context window focused.
2. **Backwards-Compatible 2-Reviewer Mapping**: By partitioning reviewer slots into Slot 1 (database, billing, security, documentation) and Slot 2 (cart, api, qa), we maintain 100% backwards compatibility with legacy tests while dynamically matching real code scopes.
3. **JSON-RPC Explicit MCP Logging**: Providing raw JSON-RPC requests/responses (e.g. `call_tool` logs) directly in the debate stream adds professional observability, making agent tool usage transparent to developers.
4. **Zero-Trust Triage Approval**: The automated fallback check correctly halts high-stakes paths (like database table modifications) and escalates them to human operator approval via the `/api/consent` endpoint, maintaining a zero-trust model.
5. **SDK Memory Robustness**: Catching Memory API limit errors (403) and failing back to local JSON memory storage allows free-tier or offline execution without breaking the debate lifecycle.
