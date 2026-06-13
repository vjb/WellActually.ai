import os
import sys
import asyncio
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure root path is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.swarm import SwarmSession, CoderAgent, ReviewerAgent, Agent
from src.governance import verify_schema_compliance, verify_openapi_compliance, verify_rbac_compliance, TelemetryScanner

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

    def add_event(self, message: str, sender: str = "SYSTEM", role: str = "SYSTEM", level: str = "info"):
        self.events.append({
            "timestamp": time.time(),
            "sender": sender,
            "role": role,
            "message": message,
            "level": level
        })

state = SwarmState()
start_lock = asyncio.Lock()

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
    
    if triage_res["status"] == "PENDING_HUMAN_APPROVAL":
        state.status = "PENDING_HUMAN_APPROVAL"
        state.add_event("❌ Zero-Trust Check FAILED: High-stakes paths matched. Automatic merge halted.", sender="TriageScanner", level="warning")
        state.add_event("Waiting for human operator manual approval to proceed...", level="warning")
        
        # Block until human consent
        while state.human_consent is None:
            if is_stale():
                return  # State was reset, abandon this simulation
            await asyncio.sleep(0.5)
            
        if not state.human_consent:
            state.status = "HALTED"
            state.add_event("⚠️ Human Operator REJECTED the compliance exception. Swarm terminated.", level="error")
            return
            
        state.add_event("✓ Human Operator APPROVED the compliance exception. Proceeding with swarm review.", level="info")
        state.human_consent = None  # Reset for future steps
        
    # 2. Run MCP & Telemetry Static Checks to populate dashboard early
    state.add_event("Scanning log stream for active anomalies...", sender="WatchdogDaemon", level="info")
    anomalies = session.run_watchdog_scan()
    state.watchdog_logs = anomalies
    for a in anomalies:
        state.add_event(f"Anomaly detected in {a['service']}: {a['message']}", sender="TelemetryScanner", level="warning")
        
    # 3. Setup agents and run debate
    state.status = "RUNNING"
    state.add_event("Initializing Band.ai remote agent credentials...", level="info")
    await asyncio.sleep(1.0)
    
    unique_suffix = session.unique_suffix
    conductor = Agent(name=f"conductor-{unique_suffix}", role="Orchestrator", system_prompt="You are the Conductor orchestrating the debate.")
    coder = CoderAgent(name_suffix=unique_suffix, model="gpt-4o-mini", scenario=state.scenario)
    reviewer_auth = ReviewerAgent(role="Auth & Fraud SME", name_suffix=unique_suffix, model="unsloth/Meta-Llama-3.1-70B-Instruct", domain="auth")
    reviewer_cart = ReviewerAgent(role="Cart SME", name_suffix=unique_suffix, model="gpt-4o-mini", domain="cart")
    
    try:
        await session.initialize_session(conductor, coder, [reviewer_auth, reviewer_cart])
        state.room_id = session.room_id
        state.add_event(f"Band.ai Task Room successfully created. ID: {session.room_id}", sender=conductor.name, role=conductor.role, level="info")
        
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
            state.schema_check = verify_schema_compliance(state.current_code, session.schema_path)
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
                
            if round_res["is_deadlocked"]:
                state.status = "HALTED"
                state.add_event("⚠️ Swarm consensus reached deadlock! Round limit exceeded.", level="error")
                state.add_event("Halt event published to Band.ai room. Escalating to Human Operator...", level="error")
                
                # Wait for Human Consent Override
                state.human_consent = None
                while state.human_consent is None:
                    await asyncio.sleep(0.5)
                    
                if state.human_consent:
                    state.status = "COMPLETED"
                    state.resolution_type = "human_override"
                    state.add_event("✓ Human Operator OVERRODE the deadlock and approved the PR.", level="info")
                else:
                    state.status = "HALTED"
                    state.resolution_type = "halted"
                    state.add_event("❌ Human Operator agreed with SME and REJECTED the PR.", level="error")
                break
                
            if round_res["round_passed"]:
                state.status = "COMPLETED"
                state.resolution_type = "consensus"
                state.add_event("✓ Swarm Consensus reached! Code compliance checks passed.", level="info")
                break
                
        # Safety net: if loop exhausted without consensus, escalate to HALTED
        if state.status == "RUNNING":
            state.status = "HALTED"
            state.add_event("⚠️ Swarm consensus reached deadlock! Round limit exceeded.", level="error")
            state.add_event("Halt event published to Band.ai room. Escalating to Human Operator...", level="error")
            
            # Wait for Human Consent Override
            state.human_consent = None
            while state.human_consent is None:
                await asyncio.sleep(0.5)
                
            if state.human_consent:
                state.status = "COMPLETED"
                state.resolution_type = "human_override"
                state.add_event("✓ Human Operator OVERRODE the deadlock and approved the PR.", level="info")
            else:
                state.status = "HALTED"
                state.resolution_type = "halted"
                state.add_event("❌ Human Operator agreed with SME and REJECTED the PR.", level="error")
    except Exception as e:
        state.status = "CRASHED"
        state.add_event(f"💥 Swarm Execution CRASHED: {str(e)}", level="error")
        state.add_event("Zero-Fallback Mode Active. Crashed out directly on Band.ai platform limit.", level="error")
        # Ensure we run cleanup (which preserves reused agents keys)
        await session.cleanup_agents(conductor, coder, [reviewer_auth, reviewer_cart])
        raise e
        
    await session.cleanup_agents(conductor, coder, [reviewer_auth, reviewer_cart])

@app.get("/api/status")
def get_status():
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
def get_events():
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
def submit_consent(req: ConsentRequest):
    if state.status not in ["PENDING_HUMAN_APPROVAL", "HALTED", "RUNNING"]:
        raise HTTPException(status_code=400, detail=f"Cannot submit consent in state '{state.status}'.")
    state.human_consent = req.approve
    return {"status": "ok", "consent": req.approve}

@app.post("/api/reset")
def reset_state():
    if state.status == "RUNNING":
        raise HTTPException(status_code=400, detail="Cannot reset while simulation is running.")
    state.reset(scenario=state.scenario)
    return {"status": "reset"}

@app.get("/api/telemetry")
def get_telemetry():
    scanner = TelemetryScanner("mock_infrastructure/app_logs.json")
    anomalies = scanner.scan_leaks()
    return anomalies

@app.get("/api/mcp")
def get_mcp():
    code = state.current_code or "def get_spending(user_id):\n    return db.query('SELECT spending_limit_usd, discount_tier FROM billing_profiles WHERE user_id = %s', user_id)"
    schema_check = verify_schema_compliance(code, "mock_infrastructure/postgres_schema.sql")
    openapi_check = verify_openapi_compliance(code, "mock_infrastructure/openapi_contract.json")
    return {
        "postgres": schema_check,
        "openapi": openapi_check
    }
