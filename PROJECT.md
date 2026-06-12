# Project: Codeband Adversarial Governance Swarm

## Architecture
- **Configuration Layer**: `codeband.yaml` and `agent_config.yaml` defining custom agent personas (Conductor, Cart SME, Auth & Fraud SME, Inventory SME).
- **Mock Infrastructure**: Mock databases, queues, and configuration stores (`mock_infrastructure/`).
- **Governance Engine** (`src/governance.py`): Realizes programmatic compliance checks (CODEOWNERS routing, Consensus tracking, and Observability watchdog).
- **Simulation Test Suite** (`tests/test_swarm.py`): Programmatic mocks testing standard workflows, high-stakes blocking, deadlocks, and telemetry log analysis.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Setup & Verify Env | Perform environment check and verify `cb doctor` | none | DONE |
| 2 | Swarm Config & Mocks | Configure `codeband.yaml` and verify `mock_infrastructure/` | M1 | IN_PROGRESS |
| 3 | Governance Engine | Implement `src/governance.py` | M2 | IN_PROGRESS |
| 4 | Simulation Test Suite | Implement `tests/test_swarm.py` | M3 | IN_PROGRESS |
| 5 | Verify & Audit | Verify `cb doctor` and `pytest` pass all scenarios; run audit | M4 | PLANNED |

## Interface Contracts
### Governance Engine API (`src/governance.py`)
- `parse_codeowners(content: str) -> dict`: Parses `CODEOWNERS` files. Returns mapping of patterns to metadata/owners.
- `triage_pr(diff_files: list[str], codeowners_rules: dict) -> dict`: Returns triage result dictionary with keys `status` (e.g., "approved", "high-stakes_pending"), `required_approvals` (list of groups), and `is_high_stakes` (bool).
- `class ConsensusTracker`:
  - `__init__(self, max_rounds: int = 2)`
  - `record_round(self, pr_id: str, outcome: str) -> dict`: Records outcome. Returns dict with keys `is_deadlocked` (bool) and `action` (e.g., "continue", "hitl_escalation").
- `class TelemetryScanner`:
  - `__init__(self, log_path: str)`
  - `scan_leaks(self) -> list[dict]`: Parses logs, returns list of detected memory leak logs or alerts.

## Code Layout
- `codeband.yaml` - Main Codeband orchestration and guidelines configuration.
- `agent_config.yaml` - Custom agent credentials and ID configuration.
- `mock_infrastructure/` - Schema, layout, owners, and telemetry logs.
- `src/governance.py` - Core logic for triage, consensus, and observability.
- `tests/test_swarm.py` - Automated scenario test cases.
