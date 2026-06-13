import os
import sys
import asyncio
import time
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure root path is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.swarm import SwarmSession, CoderAgent, ReviewerAgent, Agent, post_github_pr_comment
from src.governance import verify_schema_compliance, verify_openapi_compliance, verify_rbac_compliance, TelemetryScanner

logger = logging.getLogger("FastAPIServer")

def format_scorecard_comment(state) -> str:
    """Formats the markdown scorecard comment to post to GitHub."""
    # Emoji indicators based on compliance status
    def get_emoji(check):
        if not check:
            return "❔ N/A"
        return "✅ Passed" if check.get("compliant", False) else "❌ Failed"
        
    schema_emoji = get_emoji(state.schema_check)
    openapi_emoji = get_emoji(state.openapi_check)
    rbac_emoji = get_emoji(state.rbac_check)
    
    # Format violations lists
    def format_violations(check):
        if not check or not check.get("violations"):
            return "No violations."
        return "\n".join(f"- {v}" for v in check["violations"])

    schema_violations = format_violations(state.schema_check)
    openapi_violations = format_violations(state.openapi_check)
    rbac_violations = format_violations(state.rbac_check)
    
    # Format anomalies list
    if state.watchdog_logs:
        anomalies_str = "\n".join(f"- **{a['service']}**: {a['message']}" for a in state.watchdog_logs)
    else:
        anomalies_str = "No anomalies detected."
        
    # Format debate rounds summary
    debate_rounds_info = f"Adversarial debate completed in {state.consensus_round} rounds."
    if state.debate_summary:
        round_hist = state.debate_summary.get("round_history", [])
        if round_hist:
            debate_rounds_info += "\n" + "\n".join(
                f"- **Round {r.get('round')}:** {r.get('outcome', 'unknown').upper()}"
                for r in round_hist
            )

    triage_info = "Status: OK"
    if state.triage_result:
        triage_status = state.triage_result.get("status")
        req_approvals = ", ".join(state.triage_result.get("required_approvals", []))
        if triage_status == "PENDING_HUMAN_APPROVAL":
            triage_info = f"⚠️ Zero-Trust Check FAILED. Halted for human approval.\n- **Required approvals:** {req_approvals}"
        else:
            triage_info = f"✅ Clean triage. Status: {triage_status}"

    body = f"""# 🛡️ Governance Swarm Audit Scorecard: {state.pr_id}

### 📊 Simulation Summary
- **Scenario:** `{state.scenario}`
- **Status:** `{state.status}`
- **Resolution:** `{state.resolution_type or 'N/A'}`
- **Consensus Rounds:** `{state.consensus_round}`

### 🔒 Triage Compliance Results
{triage_info}

### 🛠️ Code Verification Checks
| Check Category | Compliance Status | Details |
| :--- | :--- | :--- |
| **PostgreSQL Schema Compliance** | {schema_emoji} | AST SQL column check |
| **OpenAPI Contract Compliance** | {openapi_emoji} | Endpoint path/payload check |
| **Middleware RBAC Check** | {rbac_emoji} | Sensitive financial column role verification |

#### 📁 Schema Violations
{schema_violations}

#### 📁 OpenAPI Violations
{openapi_violations}

#### 📁 RBAC Violations
{rbac_violations}

### 🚨 Telemetry Watchdog Scanner
{anomalies_str}

### 💬 Consensus Debate History
{debate_rounds_info}
"""
    return body


# Scenario configuration — single layered scenario for demo
SCENARIO_CONFIG = {
    "rbac_bypass": {
        "pr_id": "PR-217",
        "diff_files": ["src/billing/spending_report.py"],
        "description": "RBAC Bypass: Stale docs hide a removed column and a revoked access policy",
        "mcp_targets": {
            "schema_table": "billing_profiles",
            "api_endpoint": "/api/v1/billing/spending",
            "rbac_target": "billing_profiles.spending_limit_usd",
        },
    },
}

app = FastAPI(title="Swarm Control Center Backend", version="1.0.0")

# Enable CORS for frontend development (restrict origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # DEMO: restrict to dev servers
    allow_methods=["*"],
    allow_headers=["*"],
)

class SwarmState:
    def __init__(self):
        self.status = "IDLE"  # IDLE, TRIAGE, PENDING_HUMAN_APPROVAL, RUNNING, HALTED, COMPLETED, CRASHED
        self.events: List[Dict[str, Any]] = []
        self.scenario = "rbac_bypass"
        self.pr_id = "PR-217"
        self.diff_files = ["src/billing/spending_report.py"]
        self.triage_result: Optional[Dict[str, Any]] = None
        self.human_consent: Optional[bool] = None  # True=Approve, False=Reject, None=Pending
        self.watchdog_logs: List[Dict[str, Any]] = []
        self.schema_check: Optional[Dict[str, Any]] = None
        self.openapi_check: Optional[Dict[str, Any]] = None
        self.rbac_check: Optional[Dict[str, Any]] = None
        self.current_code: Optional[str] = None
        self.consensus_round = 0
        self.room_id: Optional[str] = None
        self.debate_summary: Optional[Dict[str, Any]] = None
        self.resolution_type: Optional[str] = None  # "consensus" | "human_override" | "halted"
        self.initial_schema_check: Optional[Dict[str, Any]] = None  # Round 1 snapshot
        self.initial_openapi_check: Optional[Dict[str, Any]] = None
        self.initial_rbac_check: Optional[Dict[str, Any]] = None
        self.mcp_targets: Optional[Dict[str, Any]] = None
        self.generation = 0  # Incremented on reset to detect stale simulation tasks

    def save_state(self):
        """Serializes the current SwarmState to a local mock database file."""
        state_dict = {
            "status": self.status,
            "scenario": self.scenario,
            "pr_id": self.pr_id,
            "diff_files": self.diff_files,
            "triage_result": self.triage_result,
            "consensus_round": self.consensus_round,
            "room_id": self.room_id,
            "current_code": self.current_code,
            "schema_check": self.schema_check,
            "openapi_check": self.openapi_check,
            "rbac_check": self.rbac_check,
            "debate_summary": self.debate_summary,
            "resolution_type": self.resolution_type,
            "initial_schema_check": self.initial_schema_check,
            "initial_openapi_check": self.initial_openapi_check,
            "initial_rbac_check": self.initial_rbac_check,
            "mcp_targets": self.mcp_targets,
            "generation": self.generation,
            "human_consent": self.human_consent,
            "events": self.events,
            "watchdog_logs": self.watchdog_logs
        }
        try:
            os.makedirs("mock_infrastructure", exist_ok=True)
            with open("mock_infrastructure/session_state.json", "w", encoding="utf-8") as f:
                json.dump(state_dict, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state to session_state.json: {e}")

    def reset(self, scenario: str = "rbac_bypass"):
        self.status = "IDLE"
        self.events = []
        self.scenario = scenario
        cfg = SCENARIO_CONFIG.get(scenario, SCENARIO_CONFIG["rbac_bypass"])
        self.pr_id = cfg["pr_id"]
        self.diff_files = cfg["diff_files"]
        self.triage_result = None
        self.human_consent = None
        self.watchdog_logs = []
        self.schema_check = None
        self.openapi_check = None
        self.rbac_check = None
        self.current_code = None
        self.consensus_round = 0
        self.room_id = None
        self.debate_summary = None
        self.resolution_type = None
        self.initial_schema_check = None
        self.initial_openapi_check = None
        self.initial_rbac_check = None
        self.mcp_targets = cfg.get("mcp_targets")
        self.generation += 1  # Invalidate any running simulation tasks
        self.save_state()

    def add_event(self, message: str, sender: str = "SYSTEM", role: str = "SYSTEM", level: str = "info"):
        self.events.append({
            "timestamp": time.time(),
            "sender": sender,
            "role": role,
            "message": message,
            "level": level
        })
        self.save_state()

state = SwarmState()
start_lock = asyncio.Lock()
consent_events: Dict[str, asyncio.Event] = {}

def get_consent_event(pr_id: str) -> asyncio.Event:
    if pr_id not in consent_events:
        consent_events[pr_id] = asyncio.Event()
    return consent_events[pr_id]

class ConsentRequest(BaseModel):
    approve: bool

async def run_simulation_task():
    task_generation = state.generation  # Capture to detect if state was reset during our run
    
    def is_stale():
        return state.generation != task_generation
    
    state.add_event(f"Pull Request {state.pr_id} received.", level="info")
    state.add_event("Modified files: " + str(state.diff_files), level="info")
    state.add_event('[JIRA INTEGRATION] Fetched context for Ticket SEC-842: "Implement spending report fetcher. MUST use standard rbac.check_access() middleware."', level="info")
    state.add_event(f"Scenario: {SCENARIO_CONFIG[state.scenario]['description']}", level="info")
    
    # 1. Triage compliance
    state.status = "TRIAGE"
    state.add_event("Running compliance triage scanner...", level="info")
    await asyncio.sleep(1.0)
    
    session = SwarmSession(
        pr_id=state.pr_id,
        diff_files=state.diff_files,
        codeowners_path="mock_infrastructure/CODEOWNERS",
        schema_path="mock_infrastructure/postgres_schema.sql",
        openapi_path="mock_infrastructure/openapi_contract.json",
        log_path="mock_infrastructure/app_logs.json"
    )
    
    triage_res = session.run_triage()
    state.triage_result = triage_res
    state.save_state()
    
    if triage_res["status"] == "PENDING_HUMAN_APPROVAL":
        state.status = "PENDING_HUMAN_APPROVAL"
        state.add_event("❌ Zero-Trust Check FAILED: High-stakes paths matched. Automatic merge halted.", sender="TriageScanner", level="warning")
        state.add_event("Waiting for human operator manual approval to proceed...", level="warning")
        state.save_state()
        
        # Block until human consent using asyncio.Event
        pr_event = get_consent_event(state.pr_id)
        pr_event.clear()
        await pr_event.wait()
        if is_stale():
            return  # State was reset, abandon this simulation
            
        if not state.human_consent:
            state.status = "HALTED"
            state.add_event("⚠️ Human Operator REJECTED the compliance exception. Swarm terminated.", level="error")
            state.save_state()
            return
            
        state.add_event("✓ Human Operator APPROVED the compliance exception. Proceeding with swarm review.", level="info")
        state.human_consent = None  # Reset for future steps
        state.save_state()
        
    # 2. Run MCP & Telemetry Static Checks to populate dashboard early
    state.add_event("Scanning log stream for active anomalies...", sender="WatchdogDaemon", level="info")
    anomalies = session.run_watchdog_scan()
    state.watchdog_logs = anomalies
    for a in anomalies:
        state.add_event(f"Anomaly detected in {a['service']}: {a['message']}", sender="TelemetryScanner", level="warning")
    state.save_state()
        
    # 3. Setup agents and run debate
    state.status = "RUNNING"
    state.add_event("Initializing Band.ai remote agent credentials...", level="info")
    await asyncio.sleep(1.0)
    
    unique_suffix = session.unique_suffix
    conductor = Agent(name=f"conductor-{unique_suffix}", role="Orchestrator", system_prompt="You are the Conductor orchestrating the debate.")
    coder = CoderAgent(name_suffix=unique_suffix, model="gpt-4o-mini", scenario=state.scenario)
    reviewer_auth = ReviewerAgent(role="Auth & Fraud SME", name_suffix=unique_suffix, model="unsloth/Meta-Llama-3.1-70B-Instruct", domain="auth")
    reviewer_cart = ReviewerAgent(role="Cart SME", name_suffix=unique_suffix, model="gpt-4o-mini", domain="cart")
    state.save_state()
    
    try:
        await session.initialize_session(conductor, coder, [reviewer_auth, reviewer_cart])
        state.room_id = session.room_id
        state.add_event(f"Band.ai Task Room successfully created. ID: {session.room_id}", sender=conductor.name, role=conductor.role, level="info")
        state.save_state()
        
        MAX_ROUNDS = 2
        for round_num in range(1, MAX_ROUNDS + 1):
            state.consensus_round = round_num
            state.add_event(f"Starting Adversarial Debate Round {round_num}...", level="info")
            await asyncio.sleep(1.0)
            
            # Execute round
            round_res = await session.run_debate_round(conductor, coder, [reviewer_auth, reviewer_cart])
            
            # Extract proposed code
            state.current_code = round_res["coder_response"]
            
            # Run compliance verification for visual feedback
            state.schema_check = await asyncio.to_thread(verify_schema_compliance, state.current_code, session.schema_path)
            state.openapi_check = verify_openapi_compliance(state.current_code, session.openapi_path)
            state.rbac_check = verify_rbac_compliance(state.current_code)
            
            # Preserve Round 1 checks as the "initial scan" for the MCP panel story
            if round_num == 1:
                state.initial_schema_check = state.schema_check
                state.initial_openapi_check = state.openapi_check
                state.initial_rbac_check = state.rbac_check
            
            # Log Coder proposal
            state.add_event(round_res["coder_response"], sender=coder.name, role=coder.role, level="info")
            
            # Log Reviews
            for name, role, review in round_res["reviewer_responses"]:
                lvl = "error" if ("❌" in review or "FAILED" in review) else "info"
                state.add_event(review, sender=name, role=role, level=lvl)
            
            # Store debate summary for frontend analytics card
            state.debate_summary = round_res.get("debate_summary")
            state.save_state()
                
            if round_res["is_deadlocked"]:
                state.status = "HALTED"
                state.add_event("⚠️ Swarm consensus reached deadlock! Round limit exceeded.", level="error")
                state.add_event("Halt event published to Band.ai room. Escalating to Human Operator...", level="error")
                state.save_state()
                
                # Wait for Human Consent Override
                state.human_consent = None
                pr_event = get_consent_event(state.pr_id)
                pr_event.clear()
                await pr_event.wait()
                if is_stale():
                    return
                    
                if state.human_consent:
                    state.status = "COMPLETED"
                    state.resolution_type = "human_override"
                    state.add_event("✓ Human Operator OVERRODE the deadlock and approved the PR.", level="info")
                else:
                    state.status = "HALTED"
                    state.resolution_type = "halted"
                    state.add_event("❌ Human Operator agreed with SME and REJECTED the PR.", level="error")
                state.save_state()
                break
                
            if round_res["round_passed"]:
                state.status = "COMPLETED"
                state.resolution_type = "consensus"
                state.add_event("✓ Swarm Consensus reached! Code compliance checks passed.", level="info")
                state.save_state()
                break
                
        # Safety net: if loop exhausted without consensus, escalate to HALTED
        if state.status == "RUNNING":
            state.status = "HALTED"
            state.add_event("⚠️ Swarm consensus reached deadlock! Round limit exceeded.", level="error")
            state.add_event("Halt event published to Band.ai room. Escalating to Human Operator...", level="error")
            state.save_state()
            
            # Wait for Human Consent Override
            state.human_consent = None
            pr_event = get_consent_event(state.pr_id)
            pr_event.clear()
            await pr_event.wait()
            if is_stale():
                return
                
            if state.human_consent:
                state.status = "COMPLETED"
                state.resolution_type = "human_override"
                state.add_event("✓ Human Operator OVERRODE the deadlock and approved the PR.", level="info")
            else:
                state.status = "HALTED"
                state.resolution_type = "halted"
                state.add_event("❌ Human Operator agreed with SME and REJECTED the PR.", level="error")
            state.save_state()
    except Exception as e:
        state.status = "CRASHED"
        state.add_event(f"💥 Swarm Execution CRASHED: {str(e)}", level="error")
        state.add_event("Zero-Fallback Mode Active. Crashed out directly on Band.ai platform limit.", level="error")
        state.save_state()
        # Ensure we run cleanup (which preserves reused agents keys)
        await session.cleanup_agents(conductor, coder, [reviewer_auth, reviewer_cart])
        raise e
    # Post scorecard to GitHub PR
    try:
        comment_body = format_scorecard_comment(state)
        await asyncio.to_thread(post_github_pr_comment, state.pr_id, comment_body)
    except Exception as ge:
        logger.error(f"Failed to post GitHub PR comment: {ge}")

    await session.cleanup_agents(conductor, coder, [reviewer_auth, reviewer_cart])
    state.save_state()


@app.get("/api/status")
async def get_status():
    return {
        "status": state.status,
        "scenario": state.scenario,
        "pr_id": state.pr_id,
        "diff_files": state.diff_files,
        "triage_result": state.triage_result,
        "consensus_round": state.consensus_round,
        "room_id": state.room_id,
        "current_code": state.current_code,
        "schema_check": state.schema_check,
        "openapi_check": state.openapi_check,
        "rbac_check": state.rbac_check,
        "debate_summary": state.debate_summary,
        "resolution_type": state.resolution_type,
        "initial_schema_check": state.initial_schema_check,
        "initial_openapi_check": state.initial_openapi_check,
        "initial_rbac_check": state.initial_rbac_check,
        "mcp_targets": state.mcp_targets
    }

@app.get("/api/events")
async def get_events():
    return state.events

class StartRequest(BaseModel):
    scenario: str = "rbac_bypass"

@app.post("/api/start")
async def start_simulation(background_tasks: BackgroundTasks, req: StartRequest = StartRequest()):
    async with start_lock:
        if state.status not in ["IDLE", "COMPLETED", "HALTED", "CRASHED"]:
            raise HTTPException(status_code=400, detail="Simulation is already running.")
        if req.scenario not in SCENARIO_CONFIG:
            raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}. Choose from: {list(SCENARIO_CONFIG.keys())}")
        state.reset(scenario=req.scenario)
        background_tasks.add_task(run_simulation_task)
        return {"status": "started", "scenario": req.scenario}

@app.post("/api/consent")
async def submit_consent(req: ConsentRequest):
    if state.status not in ["PENDING_HUMAN_APPROVAL", "HALTED", "RUNNING"]:
        raise HTTPException(status_code=400, detail=f"Cannot submit consent in state '{state.status}'.")
    state.human_consent = req.approve
    state.save_state()
    get_consent_event(state.pr_id).set()  # Wake up any waiting coroutines
    return {"status": "ok", "consent": req.approve}

@app.post("/api/reset")
async def reset_state():
    if state.status == "RUNNING":
        raise HTTPException(status_code=400, detail="Cannot reset while simulation is running.")
    old_pr_id = state.pr_id
    state.reset(scenario=state.scenario)
    get_consent_event(old_pr_id).set()  # Wake up any waiting coroutines to let them exit
    return {"status": "reset"}

@app.get("/api/telemetry")
async def get_telemetry():
    scanner = TelemetryScanner("mock_infrastructure/app_logs.json")
    anomalies = scanner.scan_leaks()
    return anomalies

@app.get("/api/mcp")
async def get_mcp():
    code = state.current_code or "def get_spending(user_id):\n    return db.query('SELECT spending_limit_usd, discount_tier FROM billing_profiles WHERE user_id = %s', user_id)"
    schema_check = await asyncio.to_thread(verify_schema_compliance, code, "mock_infrastructure/postgres_schema.sql")
    openapi_check = verify_openapi_compliance(code, "mock_infrastructure/openapi_contract.json")
    return {
        "postgres": schema_check,
        "openapi": openapi_check
    }
