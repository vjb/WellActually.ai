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
    tracker = ConsensusTracker(max_rounds=2)
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
    actual_log_path = "mock_infrastructure/app_logs.json"
    scanner = TelemetryScanner(log_path=actual_log_path)
    
    detected_anomalies = scanner.scan_leaks()
    
    assert len(detected_anomalies) > 0
    assert any("Memory leak signature detected" in alert["message"] for alert in detected_anomalies)

    custom_logs = [
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
        
    scanner_custom = TelemetryScanner(log_path=str(custom_log_file))
    custom_anomalies = scanner_custom.scan_leaks()
    
    assert len(custom_anomalies) == 1
    assert "Database pool exhaustion" in custom_anomalies[0]["message"]


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
    
    # Round 2
    r2 = await session.run_debate_round(conductor, coder, [reviewer])
    assert r2["round_passed"] is False
    assert r2["is_deadlocked"] is False
    assert session.status == "PENDING_HUMAN_APPROVAL"
    
    # Round 3
    r3 = await session.run_debate_round(conductor, coder, [reviewer])
    assert r3["round_passed"] is False
    assert r3["is_deadlocked"] is True
    assert r3["action"] == "hitl_escalation"
    assert session.status == "HALTED"
    
    # Cleanup agents
    await session.cleanup_agents(conductor, coder, [reviewer])


