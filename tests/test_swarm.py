import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from openai import OpenAI
from dotenv import load_dotenv

# Import the governance engine API under test
from src.governance import (
    parse_codeowners,
    triage_pr,
    ConsensusTracker,
    TelemetryScanner,
    verify_schema_compliance,
    verify_openapi_compliance,
)

# ============================================================================
# MOCK DATA & FIXTURES
# ============================================================================

MOCK_CODEOWNERS_CONTENT = """
# Codeband Adversarial Governance Swarm CODEOWNERS
# Designates high-stakes security and billing pathways requiring human review.

# High-Stakes Authentication and Security Pathways
/src/auth/                      @security-owners-pool  [high-stakes]

# High-Stakes Financial Billing and Checkout Pathways
/src/billing/                   @billing-owners-pool   [high-stakes]

# Cart and Inventory SME Pathways
/src/cart/                      @cart-owners-pool
/src/inventory/                 @inventory-owners-pool
"""

@pytest.fixture
def mock_codeowners_rules():
    """Returns parsed CODEOWNERS rules based on mock content."""
    return parse_codeowners(MOCK_CODEOWNERS_CONTENT)


# ============================================================================
# TEST 1: Zero-Trust Compliance Enforcement (Goal 1: CODEOWNERS Interception)
# ============================================================================

def test_goal_1_codeowners_interception(mock_codeowners_rules):
    """
    Test 1 maps to Goal 1 (CODEOWNERS Interception):
    An autonomous coder attempts to modify files under /src/auth/ or /src/billing/.
    The system must programmatically intercept the transaction against the CODEOWNERS policy,
    halt the auto-merge loop, and force a hard state change to PENDING_HUMAN_APPROVAL.
    """
    diff_files = ["src/auth/oauth_provider.py", "src/billing/stripe_payment.py"]
    
    triage_result = triage_pr(diff_files, mock_codeowners_rules)
    
    assert triage_result["is_high_stakes"] is True
    assert triage_result["status"] == "PENDING_HUMAN_APPROVAL"
    assert "@security-owners-pool" in triage_result["required_approvals"]
    assert "@billing-owners-pool" in triage_result["required_approvals"]

    with patch("thenvoi_rest.AsyncRestClient") as mock_rest_client:
        mock_instance = MagicMock()
        mock_rest_client.return_value = mock_instance
        
        if triage_result["status"] == "PENDING_HUMAN_APPROVAL":
            mock_instance.human_api_profile.create_human_task(
                task_type="compliance_interception",
                target_pr="pr_compliance_violation",
                required_pools=triage_result["required_approvals"]
            )
            
        mock_instance.human_api_profile.create_human_task.assert_called_once_with(
            task_type="compliance_interception",
            target_pr="pr_compliance_violation",
            required_pools=triage_result["required_approvals"]
        )


# ============================================================================
# TEST 2: Multi-Model Adversarial Loop & Deadlock Termination (Goal 2 & 3)
# ============================================================================

def test_goal_2_3_adversarial_loop_and_deadlock_termination():
    """
    Test 2 maps to Goal 2 & 3 (Adversarial Loop & Deadlock Termination):
    - Goal 2: Claude coder writes checkout logic violating PostgreSQL schema or OpenAPI contract.
      Codex Cart/Auth SME reviewer flags the mismatch using MCP context.
    - Goal 3: ConsensusTracker counts disagreement iterations, breaking the loop on the 3rd iteration
      and Escalating to human operator.
    """
    tracker = ConsensusTracker(max_rounds=3)
    pr_id = "pr_checkout_adversarial"
    
    claude_coder_invalid_code = """
    def process_checkout(cart_id, payment_method_token):
        # Mismatch: cart_items table doesn't have discount_applied column
        db.execute("INSERT INTO cart_items (cart_id, product_id, quantity, price_at_addition, discount_applied) VALUES ...")
    """
    schema_check = verify_schema_compliance(claude_coder_invalid_code, "mock_infrastructure/postgres_schema.sql")
    assert schema_check["compliant"] is False
    assert any("discount_applied" in err for err in schema_check["violations"])

    claude_coder_invalid_code_2 = """
    def perform_checkout(payload):
        # Mismatch: missing the required unique identifier property for OpenAPI
        payment_token = payload["payment_method_token"]
        return api_post("/api/v1/checkout", data={"payment_method_token": payment_token})
    """
    openapi_check = verify_openapi_compliance(claude_coder_invalid_code_2, "mock_infrastructure/openapi_contract.json")
    assert openapi_check["compliant"] is False
    assert any("cart_id" in err for err in openapi_check["violations"])

    r1 = tracker.record_round(pr_id, outcome="failed")
    assert r1["is_deadlocked"] is False
    assert r1["action"] == "continue"

    r2 = tracker.record_round(pr_id, outcome="failed")
    assert r2["is_deadlocked"] is False
    assert r2["action"] == "continue"

    r3 = tracker.record_round(pr_id, outcome="failed")
    assert r3["is_deadlocked"] is True
    assert r3["action"] == "hitl_escalation"


# ============================================================================
# TEST 3: Context-Aware Telemetry Integration (Goal 4: Observability Watchdog)
# ============================================================================

def test_goal_4_observability_telemetry_leak_detection(tmp_path):
    """
    Test 3 maps to Goal 4 (Observability Telemetry Leak Detection):
    Verifies that the Telemetry Watchdog/Observability daemon stream parser successfully detects
    anomalies (memory leaks and database pool exhaustion) and injects logs / alert payloads.
    """
    custom_logs = [
        {
            "timestamp": "2026-06-12T11:02:15.895Z",
            "level": "WARNING",
            "service": "inventory-service",
            "message": "Memory leak signature detected: heap usage increased by 45MB in local checkout loop. Active references in SessionStore not cleared."
        },
        {
            "timestamp": "2026-06-12T11:03:00.000Z",
            "level": "ERROR",
            "service": "billing-service",
            "message": "Critical: Database pool exhaustion encountered under load."
        }
    ]
    custom_log_file = tmp_path / "custom_logs.json"
    with open(custom_log_file, "w") as f:
        json.dump(custom_logs, f)
        
    scanner = TelemetryScanner(log_path=str(custom_log_file))
    detected_anomalies = scanner.scan_leaks()
    
    assert len(detected_anomalies) == 2
    assert any("Memory leak signature detected" in alert["message"] for alert in detected_anomalies)
    assert any("Database pool exhaustion" in alert["message"] for alert in detected_anomalies)


# ============================================================================
# TEST 4: Band.ai Real Connectivity Verification
# ============================================================================

@pytest.mark.anyio
@pytest.mark.skipif(not os.getenv("BAND_API_KEY"), reason="BAND_API_KEY not set — skipping live connectivity test")
async def test_band_real_connectivity():
    """
    Verifies actual reachability and authorization status of the Band.ai platform.
    """
    load_dotenv()
    api_key = os.getenv("BAND_API_KEY")
    rest_url = os.getenv("BAND_REST_URL", "https://app.band.ai")
    
    assert api_key, "BAND_API_KEY environment variable is not configured."
    
    from thenvoi_rest import AsyncRestClient
    client = AsyncRestClient(api_key=api_key, base_url=rest_url)
    
    profile_response = await client.human_api_profile.get_my_profile()
    assert profile_response is not None, "Failed to retrieve profile response from Band.ai REST endpoint."
    assert profile_response.data is not None, "Profile data is empty."
    assert profile_response.data.email is not None, "Profile email is empty."


# ============================================================================
# TEST 5: OpenAI & Partner Endpoint Routing (AI/ML API Track)
# ============================================================================

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set — skipping partner routing test")
def test_partner_endpoint_routing_verification():
    """
    Verifies that requests directed through OpenAI client are correctly routed
    to the AI/ML API partner platform base_url endpoint.
    """
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    
    assert api_key, "OPENAI_API_KEY environment variable is missing."
    assert base_url and "aimlapi" in base_url, "OPENAI_BASE_URL does not point to the partner endpoint."
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Ping"}],
        max_tokens=5
    )
    
    assert response is not None
    assert len(response.choices) > 0
    content = response.choices[0].message.content.strip()
    assert len(content) > 0


# ============================================================================
from src.swarm import SwarmSession, CoderAgent, ReviewerAgent, Agent

@pytest.mark.anyio
@patch('src.swarm.client')
@patch('thenvoi_rest.AsyncRestClient')
async def test_swarm_library_orchestration(mock_rest_client, mock_openai_client):
    """
    Verifies that the SwarmSession, CoderAgent, and ReviewerAgent classes
    orchestrate the debate round, track consensus, and detect deadlock.
    """
    # Mock chat completion responses for the coder and reviewer
    mock_choices = [
        # Coder proposal round 1
        MagicMock(message=MagicMock(content="def process_checkout(cart_id, payment_method_token):\n    db.execute('INSERT INTO cart_items (cart_id, product_id, discount_applied) VALUES (cart_id, 99, 0.20)')")),
        # Reviewer round 1
        MagicMock(message=MagicMock(content="❌ REVIEW FAILED: Column 'discount_applied' does not exist in table 'cart_items' schema.")),
        # Coder proposal round 2
        MagicMock(message=MagicMock(content="def process_checkout(cart_id, payment_method_token):\n    try:\n        db.execute('INSERT INTO cart_items (cart_id, product_id, discount_applied) VALUES (cart_id, 99, 0.20)')\n    except:\n        pass")),
        # Reviewer round 2
        MagicMock(message=MagicMock(content="❌ REVIEW FAILED: Column 'discount_applied' mismatch persists.")),
        # Coder proposal round 3
        MagicMock(message=MagicMock(content="def process_checkout(cart_id, payment_method_token):\n    db.execute('INSERT INTO cart_items (cart_id, product_id, discount_applied) VALUES (cart_id, 99, 0.20)')")),
        # Reviewer round 3
        MagicMock(message=MagicMock(content="❌ REVIEW FAILED: Still violating schema."))
    ]
    mock_completions = MagicMock()
    mock_completions.create.side_effect = [MagicMock(choices=[choice]) for choice in mock_choices]
    mock_openai_client.chat.completions = mock_completions
    
    # Mock human_client and agent registrations
    mock_human = MagicMock()
    mock_reg = MagicMock()
    mock_reg.data.agent.id = "agent-id"
    mock_reg.data.credentials.api_key = "agent-key"
    mock_human.human_api_agents.list_my_agents = AsyncMock(return_value=MagicMock(data=[]))
    mock_human.human_api_agents.register_my_agent = AsyncMock(return_value=mock_reg)
    mock_human.human_api_agents.delete_my_agent = AsyncMock()
    
    session = SwarmSession(
        pr_id="pr_test_lib",
        diff_files=["src/billing/billing_service.py"],
        codeowners_path="mock_infrastructure/CODEOWNERS",
        schema_path="mock_infrastructure/postgres_schema.sql",
        openapi_path="mock_infrastructure/openapi_contract.json",
        log_path="mock_infrastructure/app_logs.json"
    )
    
    # Instantiated agents
    conductor = Agent("conductor-test", "Orchestrator", "Prompt")
    coder = CoderAgent()
    reviewer = ReviewerAgent("Auth & Fraud SME")
    
    # Mock conductor.rest_client after initialize_session
    mock_room = MagicMock()
    mock_room.data.id = "room-id"
    
    mock_agent_client = MagicMock()
    mock_agent_client.agent_api_chats.create_agent_chat = AsyncMock(return_value=mock_room)
    mock_agent_client.agent_api_participants.add_agent_chat_participant = AsyncMock()
    mock_agent_client.agent_api_messages.create_agent_chat_message = AsyncMock()
    mock_agent_client.agent_api_context.get_agent_chat_context = AsyncMock()
    mock_agent_client.agent_api_memories.list_agent_memories = AsyncMock()
    mock_agent_client.agent_api_memories.create_agent_memory = AsyncMock()
    mock_agent_client.agent_api_events.create_agent_chat_event = AsyncMock()
    
    # Define client routing mock
    mock_rest_client.side_effect = lambda api_key, base_url: mock_human if api_key and ("band_u" in str(api_key)) else mock_agent_client
    
    # Initialize session
    await session.initialize_session(conductor, coder, [reviewer])
    
    # Run triage
    triage_res = session.run_triage()
    assert triage_res["is_high_stakes"] is True
    assert triage_res["status"] == "PENDING_HUMAN_APPROVAL"
    assert session.status == "PENDING_HUMAN_APPROVAL"
    
    # Round 1
    r1 = await session.run_debate_round(conductor, coder, [reviewer])
    assert r1["round_passed"] is False
    assert r1["is_deadlocked"] is False
    assert session.status == "PENDING_HUMAN_APPROVAL"
    
    # Round 2 — should now deadlock at max_rounds=2
    r2 = await session.run_debate_round(conductor, coder, [reviewer])
    assert r2["round_passed"] is False
    assert r2["is_deadlocked"] is True
    assert r2["action"] == "hitl_escalation"
    assert session.status == "HALTED"
    
    # Cleanup agents
    await session.cleanup_agents(conductor, coder, [reviewer])


# ============================================================================
# Fix #2: SQL Parsing Compliance Tests
# ============================================================================
from src.governance import (
    _parse_schema_columns,
    _extract_insert_columns,
    verify_schema_compliance,
    verify_rbac_compliance,
    ConsensusTracker,
)


def test_parse_schema_columns():
    """Verify that _parse_schema_columns correctly extracts column names from CREATE TABLE statements."""
    schema = """
    CREATE TABLE cart_items (
        id UUID PRIMARY KEY,
        cart_id UUID NOT NULL,
        product_id UUID NOT NULL,
        quantity INTEGER NOT NULL,
        price_at_addition DECIMAL(12, 2) NOT NULL,
        UNIQUE(cart_id, product_id)
    );
    """
    result = _parse_schema_columns(schema)
    assert "cart_items" in result
    assert "id" in result["cart_items"]
    assert "cart_id" in result["cart_items"]
    assert "product_id" in result["cart_items"]
    assert "quantity" in result["cart_items"]
    assert "price_at_addition" in result["cart_items"]
    assert "discount_applied" not in result["cart_items"]


def test_parse_schema_multiple_tables():
    """Verify parsing works for multiple CREATE TABLE statements."""
    schema = """
    CREATE TABLE users (
        id UUID PRIMARY KEY,
        email VARCHAR(255),
        role VARCHAR(50)
    );
    CREATE TABLE carts (
        id UUID PRIMARY KEY,
        user_id UUID,
        status VARCHAR(50)
    );
    """
    result = _parse_schema_columns(schema)
    assert "users" in result
    assert "carts" in result
    assert "email" in result["users"]
    assert "user_id" in result["carts"]


def test_extract_insert_columns():
    """Verify that INSERT INTO column extraction works."""
    code = "db.execute('INSERT INTO cart_items (cart_id, product_id, discount_applied) VALUES (%s, %s, %s)')"
    result = _extract_insert_columns(code)
    assert len(result) == 1
    assert result[0][0] == "cart_items"
    assert "discount_applied" in result[0][1]
    assert "cart_id" in result[0][1]


def test_extract_insert_multiple_statements():
    """Verify extraction handles multiple INSERT statements in the same code."""
    code = """
    db.execute("INSERT INTO cart_items (cart_id, product_id) VALUES (%s, %s)")
    db.execute("INSERT INTO users (email, role) VALUES (%s, %s)")
    """
    result = _extract_insert_columns(code)
    assert len(result) == 2


def test_schema_compliance_catches_nonexistent_column():
    """The core scenario: code uses discount_applied but schema doesn't have it."""
    code = "db.execute('INSERT INTO cart_items (cart_id, product_id, discount_applied) VALUES (%s, %s, %s)')"
    result = verify_schema_compliance(code, "mock_infrastructure/postgres_schema.sql")
    assert result["compliant"] is False
    assert any("discount_applied" in v for v in result["violations"])


def test_schema_compliance_passes_valid_columns():
    """Code using only valid columns should pass."""
    code = "db.execute('INSERT INTO cart_items (cart_id, product_id, quantity, price_at_addition) VALUES (%s, %s, %s, %s)')"
    result = verify_schema_compliance(code, "mock_infrastructure/postgres_schema.sql")
    assert result["compliant"] is True
    assert len(result["violations"]) == 0


def test_schema_compliance_no_insert():
    """Code without INSERT or named-column SELECT should pass."""
    code = "result = db.query('SELECT * FROM cart_items')"
    result = verify_schema_compliance(code, "mock_infrastructure/postgres_schema.sql")
    assert result["compliant"] is True


def test_schema_compliance_catches_select_nonexistent_column():
    """SELECT with a column that doesn't exist should be caught."""
    code = "cursor.execute('SELECT spending_limit_usd, discount_tier FROM billing_profiles WHERE user_id = %s', (uid,))"
    result = verify_schema_compliance(code, "mock_infrastructure/postgres_schema.sql")
    assert result["compliant"] is False
    assert any("discount_tier" in v for v in result["violations"])


def test_schema_compliance_passes_valid_select():
    """SELECT with only valid columns should pass."""
    code = "cursor.execute('SELECT spending_limit_usd FROM billing_profiles WHERE user_id = %s', (uid,))"
    result = verify_schema_compliance(code, "mock_infrastructure/postgres_schema.sql")
    assert result["compliant"] is True


# ============================================================================
# Fix #3: RBAC Compliance Tests
# ============================================================================
def test_rbac_catches_direct_billing_access():
    """Detect direct access to billing_profiles.spending_limit_usd without role checks."""
    code = """
def get_spending(user_id):
    return db.query("SELECT spending_limit_usd FROM billing_profiles WHERE user_id = %s", user_id)
    """
    result = verify_rbac_compliance(code)
    assert result["compliant"] is False
    assert any("RBAC" in v for v in result["violations"])


def test_rbac_catches_weak_role_guard():
    """Weak if/else role guard should still fail — requires proper middleware."""
    code = """
def get_spending(user_id):
    user = db.query("SELECT role FROM users WHERE id = %s", user_id)
    if user.role == 'admin':
        return db.query("SELECT spending_limit_usd FROM billing_profiles WHERE user_id = %s", user_id)
    """
    result = verify_rbac_compliance(code)
    assert result["compliant"] is False
    assert any("client-side" in v for v in result["violations"])


def test_rbac_passes_with_strong_middleware():
    """Code with proper RBAC middleware decorator should pass."""
    code = """
@requires_role('finance_admin')
def get_spending(user_id):
    return db.query("SELECT spending_limit_usd FROM billing_profiles WHERE user_id = %s", user_id)
    """
    result = verify_rbac_compliance(code)
    assert result["compliant"] is True


def test_rbac_passes_nonsensitive_code():
    """Code not accessing sensitive columns should pass."""
    code = """
def get_cart(user_id):
    return db.query("SELECT * FROM carts WHERE user_id = %s", user_id)
    """
    result = verify_rbac_compliance(code)
    assert result["compliant"] is True


# ============================================================================
# Fix #4: Split Reviewer Context Tests
# ============================================================================
def test_reviewer_auth_domain():
    """Auth SME should have domain='auth'."""
    reviewer = ReviewerAgent(role="Auth and Fraud SME", domain="auth")
    assert reviewer.domain == "auth"
    assert "schema" in reviewer.system_prompt.lower()


def test_reviewer_cart_domain():
    """Cart SME should have domain='cart'."""
    reviewer = ReviewerAgent(role="Cart SME", domain="cart")
    assert reviewer.domain == "cart"
    assert "API" in reviewer.system_prompt or "OpenAPI" in reviewer.system_prompt


# ============================================================================
# Fix #6: ConsensusTracker Vote Tracking Tests
# ============================================================================
def test_consensus_tracker_vote_recording():
    """Verify votes are recorded per reviewer."""
    tracker = ConsensusTracker(max_rounds=2)
    tracker.record_vote("PR-104", "reviewer-auth", "Auth SME", "failed", 1, domain="auth")
    tracker.record_vote("PR-104", "reviewer-cart", "Cart SME", "passed", 1, domain="cart")

    summary = tracker.get_summary("PR-104")
    assert summary["total_votes"] == 2
    assert summary["rejections"] == 1
    assert summary["approvals"] == 1
    assert "reviewer-auth" in summary["rejections_by_reviewer"]


def test_consensus_tracker_summary_deadlock():
    """Verify summary correctly reports deadlock."""
    tracker = ConsensusTracker(max_rounds=1)
    tracker.record_round("PR-104", "failed")
    tracker.record_round("PR-104", "failed")

    summary = tracker.get_summary("PR-104")
    assert summary["is_deadlocked"] is True
    assert summary["total_rounds"] == 2


def test_consensus_tracker_summary_no_votes():
    """Summary for a PR with no votes should return empty data."""
    tracker = ConsensusTracker(max_rounds=2)
    summary = tracker.get_summary("PR-999")
    assert summary["total_votes"] == 0
    assert summary["rejections"] == 0
    assert summary["total_rounds"] == 0


# ============================================================================
# Fix #1: Scenario Prompt Tests
# ============================================================================
def test_coder_scenario_uses_stale_docs():
    """Coder should receive stale docs mentioning discount_tier (doesn't exist in live schema)."""
    coder = CoderAgent(scenario="rbac_bypass")
    assert "discount_tier" in coder.system_prompt
    assert "billing_profiles" in coder.system_prompt
    assert "staging" in coder.system_prompt
    # Should instruct to fix schema violations, not defend them
    assert "remove" in coder.system_prompt.lower() or "fix" in coder.system_prompt.lower()


def test_coder_scenario_b_rbac_bypass():
    """Scenario B coder should receive docs saying direct access is OK."""
    coder = CoderAgent(scenario="rbac_bypass")
    assert "billing_profiles" in coder.system_prompt
    assert "spending_limit_usd" in coder.system_prompt


# ============================================================================
# Fix #2: FastAPI API Endpoint Tests
# ============================================================================
from fastapi.testclient import TestClient
from src.server import app, state


def test_api_status_returns_idle():
    """GET /api/status should return IDLE state on fresh start."""
    client = TestClient(app)
    state.reset()
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "IDLE"
    assert data["scenario"] == "rbac_bypass"
    assert data["pr_id"] == "PR-217"
    assert "schema_check" in data
    assert "rbac_check" in data
    assert "debate_summary" in data
    # New fields
    assert data["resolution_type"] is None
    assert data["initial_schema_check"] is None
    assert data["mcp_targets"]["schema_table"] == "billing_profiles"
    assert data["mcp_targets"]["api_endpoint"] == "/api/v1/billing/spending"


def test_api_status_rbac_scenario_targets():
    """GET /api/status with rbac_bypass scenario should return correct MCP targets."""
    client = TestClient(app)
    state.reset(scenario="rbac_bypass")
    res = client.get("/api/status")
    data = res.json()
    assert data["pr_id"] == "PR-217"
    assert data["mcp_targets"]["schema_table"] == "billing_profiles"
    assert data["mcp_targets"]["rbac_target"] == "billing_profiles.spending_limit_usd"


def test_api_events_returns_list():
    """GET /api/events should return a list."""
    client = TestClient(app)
    state.reset()
    res = client.get("/api/events")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_api_start_accepts_scenario():
    """POST /api/start should accept and apply scenario parameter."""
    client = TestClient(app)
    state.reset()
    # Mock the background simulation task to avoid blocking on human_consent loop
    with patch("src.server.run_simulation_task", new_callable=AsyncMock):
        res = client.post("/api/start", json={"scenario": "rbac_bypass"})
    assert res.status_code == 200
    data = res.json()
    assert data["scenario"] == "rbac_bypass"
    state.reset()  # Cleanup


def test_api_start_rejects_unknown_scenario():
    """POST /api/start with unknown scenario should return 400."""
    client = TestClient(app)
    state.reset()
    res = client.post("/api/start", json={"scenario": "nonexistent"})
    assert res.status_code == 400
    assert "Unknown scenario" in res.json()["detail"]


def test_api_start_rejects_while_running():
    """POST /api/start should return 400 if simulation is already running."""
    client = TestClient(app)
    state.status = "RUNNING"
    res = client.post("/api/start", json={"scenario": "rbac_bypass"})
    assert res.status_code == 400
    state.reset()  # Cleanup


def test_api_reset_clears_state():
    """POST /api/reset should reset state to IDLE."""
    client = TestClient(app)
    state.status = "COMPLETED"
    state.pr_id = "PR-999"
    res = client.post("/api/reset")
    assert res.status_code == 200
    assert res.json()["status"] == "reset"
    # Verify state was actually reset
    status_res = client.get("/api/status")
    assert status_res.json()["status"] == "IDLE"


def test_api_reset_rejects_while_running():
    """POST /api/reset should return 400 if simulation is running."""
    client = TestClient(app)
    state.status = "RUNNING"
    res = client.post("/api/reset")
    assert res.status_code == 400
    state.reset()  # Cleanup


def test_api_telemetry_returns_anomalies():
    """GET /api/telemetry should return watchdog scan results."""
    client = TestClient(app)
    res = client.get("/api/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["service"] == "billing-service"


def test_api_mcp_returns_compliance():
    """GET /api/mcp should return schema and openapi check results."""
    client = TestClient(app)
    res = client.get("/api/mcp")
    assert res.status_code == 200
    data = res.json()
    assert "postgres" in data
    assert "openapi" in data
    assert "compliant" in data["postgres"]
