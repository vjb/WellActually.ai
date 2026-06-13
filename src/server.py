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

    auth_role = getattr(state, "reviewer_auth_role", "Auth & Fraud SME")
    cart_role = getattr(state, "reviewer_cart_role", "Cart SME")
    auth_handle = f"@reviewer-{auth_role.replace(' ', '_').replace('&', 'and').lower()}"
    cart_handle = f"@reviewer-{cart_role.replace(' ', '_').replace('&', 'and').lower()}"
    room_id = getattr(state, "room_id", None)
    room_line = f"- **Band.ai Task Room ID:** `{room_id}`" if room_id else ""

    body = f"""# 🛡️ Governance Swarm Audit Scorecard: {state.pr_id}

### 📊 Simulation Summary
- **Scenario:** `{state.scenario}`
- **Status:** `{state.status}`
- **Resolution:** `{state.resolution_type or 'N/A'}`
- **Consensus Rounds:** `{state.consensus_round}`
{room_line}

### 🤖 Band.ai Swarm Topology & Agent Identities
- **👑 Conductor Orchestrator** (`@conductor`): Routed via **AIML API** (GPT-4o-mini). Orchestrates Task Room lifecycle.
- **💻 Lead Coder** (`@coder`): Routed via **AIML API** (GPT-4o-mini). Proposes and refactors implementation draft.
- **💳 Reviewer A ({auth_role})** (`{auth_handle}`): Routed via **Featherless AI** (Unsloth Llama-3.1-70B). Audits database schema & RBAC policies using PostgreSQL verifier.
- **🏗️ Reviewer B ({cart_role})** (`{cart_handle}`): Routed via **AIML API** (GPT-4o-mini). Audits REST routes & API payloads using OpenAPI contract verifier.

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


# ── Bug 1 fix: contextual JIRA event based on PR title/files ──────────
def generate_jira_context(pr_title: str, diff_files: List[str]) -> str:
    """Generate a contextual JIRA ticket reference based on the PR's domain."""
    title_lower = (pr_title or "").lower()
    files_str = " ".join(f.lower() for f in diff_files)
    combined = f"{title_lower} {files_str}"

    if "billing" in combined or "spending" in combined:
        return 'SEC-842: "Implement spending report fetcher. MUST use standard rbac.check_access() middleware."'
    elif "auth" in combined or "oauth" in combined or "token" in combined or "login" in combined or "session" in combined:
        return 'SEC-901: "Harden OAuth2 token lifecycle. Tokens MUST be hashed before storage; revoke requires ownership check."'
    elif "checkout" in combined or "cart" in combined:
        return 'CART-315: "Refactor checkout flow. cart_id MUST be validated against OpenAPI contract before payment dispatch."'
    elif "gdpr" in combined or "export" in combined or "user_data" in combined or "user_queries" in combined or "permissions" in combined:
        return 'PRIV-208: "GDPR data export endpoint. Ownership MUST be verified; PII columns MUST be filtered from export payload."'
    elif "admin" in combined or "metrics" in combined or "dashboard" in combined:
        return 'OPS-417: "Admin metrics dashboard. Queries MUST use LIMIT clauses; PII MUST NOT leak in aggregation responses."'
    else:
        return f'ENG-100: "Review changes in {diff_files[0] if diff_files else "unknown"}. Ensure compliance with project standards."'


# ── Bug 2 fix: contextual watchdog anomaly based on PR domain ─────────
def generate_watchdog_anomalies(diff_files: List[str]) -> List[Dict[str, Any]]:
    """Generate domain-aware watchdog anomaly messages instead of hardcoded billing ones."""
    files_str = " ".join(f.lower() for f in diff_files)

    anomalies: List[Dict[str, Any]] = []
    if "billing" in files_str or "spending" in files_str:
        anomalies.append({
            "timestamp": "2026-06-12T11:03:00.000Z",
            "service": "billing-service",
            "level": "WARNING",
            "message": "Elevated query rate on billing_profiles: 847 SELECT queries in 60s from spending-report-worker. Possible missing query cache or unbounded loop.",
            "trace_id": "trace-billing-9f2e"
        })
    if "auth" in files_str or "login" in files_str or "session" in files_str or "token" in files_str or "oauth" in files_str:
        anomalies.append({
            "timestamp": "2026-06-12T11:05:22.000Z",
            "service": "auth-service",
            "level": "WARNING",
            "message": "Spike in token refresh calls from auth-session-worker: 312 refresh_token INSERTs in 30s. Possible token replay or missing dedup.",
            "trace_id": "trace-auth-4a1c"
        })
    if "gdpr" in files_str or "export" in files_str or "user_data" in files_str or "user_queries" in files_str or "permissions" in files_str:
        anomalies.append({
            "timestamp": "2026-06-12T11:08:45.000Z",
            "service": "user-data-service",
            "level": "WARNING",
            "message": "Unmasked PII detected in data-export response payload: fields [email, ssn_last4, phone] returned without redaction filter.",
            "trace_id": "trace-userdata-7b3f"
        })
    if "admin" in files_str or "metrics" in files_str or "dashboard" in files_str:
        anomalies.append({
            "timestamp": "2026-06-12T11:10:12.000Z",
            "service": "admin-service",
            "level": "WARNING",
            "message": "Unbounded SELECT * on orders table from admin-metrics-worker: query returned 2.3M rows without LIMIT. Possible OOM risk.",
            "trace_id": "trace-admin-c82d"
        })
    if "cart" in files_str or "checkout" in files_str:
        anomalies.append({
            "timestamp": "2026-06-12T11:07:33.000Z",
            "service": "checkout-service",
            "level": "WARNING",
            "message": "Payment gateway calls missing idempotency key: 47 duplicate charges detected in 5min window from checkout-handler.",
            "trace_id": "trace-checkout-e91a"
        })

    # Fallback: use static log file anomalies if nothing matched
    if not anomalies:
        anomalies.append({
            "timestamp": "2026-06-12T11:03:00.000Z",
            "service": "unknown-service",
            "level": "WARNING",
            "message": f"Anomalous activity detected in service handling {diff_files[0] if diff_files else 'unknown'}. Investigate recent changes.",
            "trace_id": "trace-generic-0000"
        })
    return anomalies


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
    "dynamic": {
        "pr_id": "PR-DYNAMIC",
        "diff_files": [],
        "description": "Dynamic PR review loaded from GitHub",
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

from typing import Tuple

def get_domain_icon_str(domain: str) -> str:
    mapping = {
        "security": "🛡️",
        "database": "🗄️",
        "documentation": "📝",
        "cart": "🛒",
        "billing": "💳",
        "api": "🔌",
        "qa": "🧪",
        "workflow": "🔄",
        "architecture": "🏗️",
        "auth": "🛡️"
    }
    return mapping.get(domain.lower(), "🔍")

def predict_reviewer_identities_list(diff_files: List[str]) -> List[Dict[str, str]]:
    """
    Predicts a list of reviewer agent identities (SMEs) based on the files touched in the PR.
    """
    categories = []
    
    has_sql = False
    has_env = False
    has_docs = False
    has_tests = False
    has_api = False
    has_billing = False
    has_cart = False
    has_auth = False
    
    for f in diff_files:
        f_lower = f.lower()
        if "schema" in f_lower or f_lower.endswith(".sql"):
            has_sql = True
        if "env" in f_lower:
            has_env = True
        if f_lower.endswith(".md") or "doc" in f_lower:
            has_docs = True
        if "test" in f_lower or f_lower.startswith("tests/"):
            has_tests = True
        if "api" in f_lower or "contract" in f_lower or f_lower.endswith(".json"):
            has_api = True
        if "billing" in f_lower or "spending" in f_lower:
            has_billing = True
        if "cart" in f_lower or "checkout" in f_lower:
            has_cart = True
        if "auth" in f_lower or "login" in f_lower or "signup" in f_lower:
            has_auth = True
            
    if has_billing:
        categories.append(("billing", "Billing & Financial SME"))
    if has_auth:
        categories.append(("auth", "Auth & Security SME"))
    if has_sql:
        categories.append(("database", "Database Schema Compliance SME"))
    if has_env:
        categories.append(("security", "Environment Configuration Security SME"))
    if has_cart:
        categories.append(("cart", "Cart & Order Integration SME"))
    if has_api:
        categories.append(("api", "API Contract & Integration SME"))
    if has_tests:
        categories.append(("qa", "QA & Test Verification SME"))
    if has_docs:
        categories.append(("documentation", "Documentation & Standards SME"))
        
    if not categories:
        categories.append(("architecture", "Code Architecture SME"))
        
    # De-duplicate categories while preserving order
    seen = set()
    unique_categories = []
    for dom, role in categories:
        if dom not in seen:
            seen.add(dom)
            unique_categories.append({"domain": dom, "role": role})
            
    return unique_categories

def predict_reviewer_identities(diff_files: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Predicts reviewer agent identities based on the files touched in the PR (returns exactly 2 reviewers for backwards compatibility).
    """
    has_sql = False
    has_env = False
    has_docs = False
    has_tests = False
    has_api = False
    has_billing = False
    has_cart = False
    has_auth = False
    
    for f in diff_files:
        f_lower = f.lower()
        if "schema" in f_lower or f_lower.endswith(".sql"):
            has_sql = True
        if "env" in f_lower:
            has_env = True
        if f_lower.endswith(".md") or "doc" in f_lower:
            has_docs = True
        if "test" in f_lower or f_lower.startswith("tests/"):
            has_tests = True
        if "api" in f_lower or "contract" in f_lower or f_lower.endswith(".json"):
            has_api = True
        if "billing" in f_lower or "spending" in f_lower:
            has_billing = True
        if "cart" in f_lower or "checkout" in f_lower:
            has_cart = True
        if "auth" in f_lower or "login" in f_lower or "signup" in f_lower:
            has_auth = True

    slot1_list = []
    if has_billing:
        slot1_list.append({"domain": "billing", "role": "Billing & Financial SME"})
    if has_auth:
        slot1_list.append({"domain": "auth", "role": "Auth & Security SME"})
    if has_sql:
        slot1_list.append({"domain": "database", "role": "Database Schema Compliance SME"})
    if has_env:
        slot1_list.append({"domain": "security", "role": "Environment Configuration Security SME"})
    if has_docs:
        slot1_list.append({"domain": "documentation", "role": "Documentation & Standards SME"})

    slot2_list = []
    if has_cart:
        slot2_list.append({"domain": "cart", "role": "Cart & Order Integration SME"})
    if has_api:
        slot2_list.append({"domain": "api", "role": "API Contract & Integration SME"})
    if has_tests:
        slot2_list.append({"domain": "qa", "role": "QA & Test Verification SME"})

    # Distribute extra Slot 1 candidates to Slot 2 if Slot 2 is empty
    if len(slot1_list) > 1 and not slot2_list:
        extra = slot1_list[1]
        if extra["domain"] == "documentation":
            slot2_list.append({"domain": "documentation", "role": "Technical Writing SME"})
        else:
            slot2_list.append(extra)
        slot1_list = [slot1_list[0]]

    if not slot1_list:
        a1 = {"domain": "auth", "role": "Auth & Security SME"}
    else:
        a1 = slot1_list[0]

    if not slot2_list:
        a2 = {"domain": "architecture", "role": "Code Architecture SME"}
    else:
        a2 = slot2_list[0]

    return a1, a2

# ── Bug 3 fix: unique system prompts per reviewer ────────────────────
# Domain-specific system prompt templates so each reviewer gets a distinct persona
REVIEWER_SYSTEM_PROMPTS = {
    "billing": (
        "You are the Billing & Financial SME. Your primary concern is financial data integrity. "
        "Audit all SQL queries touching billing_profiles, spending_limit_usd, and discount columns. "
        "Verify that RBAC middleware (rbac.check_access) guards every financial data access path. "
        "Flag any direct SELECT on sensitive monetary columns without access control."
    ),
    "auth": (
        "You are the Auth & Security SME. Your primary concern is authentication and authorization integrity. "
        "Audit token storage (must be hashed, never plaintext), session lifecycle (revocation must verify ownership), "
        "and RBAC policy enforcement. Flag hardcoded secrets, missing ownership checks, and client-side role guards."
    ),
    "database": (
        "You are the Database Schema Compliance SME. Your primary concern is schema correctness. "
        "Cross-reference every SQL column in INSERT/SELECT/UPDATE against the Postgres schema. "
        "Flag non-existent columns, SELECT * anti-patterns, and missing LIMIT on unbounded queries."
    ),
    "security": (
        "You are the Environment Configuration Security SME. Your primary concern is secrets management. "
        "Audit for hardcoded API keys, plaintext credentials, .env exposure, and missing encryption at rest."
    ),
    "cart": (
        "You are the Cart & Order Integration SME. Your primary concern is API contract compliance. "
        "Verify that all /api/v1/checkout calls match the OpenAPI contract schema. "
        "Flag missing required fields (cart_id), payload mismatches, and missing idempotency keys."
    ),
    "api": (
        "You are the API Contract & Integration SME. Your primary concern is REST endpoint correctness. "
        "Verify endpoint paths, request/response schemas, and HTTP status codes match the OpenAPI contract. "
        "Flag internal error details leaked to clients and missing input validation."
    ),
    "qa": (
        "You are the QA & Test Verification SME. Your primary concern is test coverage and correctness. "
        "Verify that test cases cover edge cases, error paths, and security boundaries. "
        "Flag missing assertions, untested branches, and tests that pass trivially."
    ),
    "documentation": (
        "You are the Documentation & Standards SME. Your primary concern is documentation accuracy. "
        "Verify that docstrings, README, and inline comments accurately reflect the current code behavior. "
        "Flag stale documentation that contradicts the implementation."
    ),
    "architecture": (
        "You are the Code Architecture SME. Your primary concern is structural quality and maintainability. "
        "Audit for separation of concerns, proper error handling, and adherence to project conventions. "
        "Flag god functions, missing abstractions, and circular dependencies."
    ),
    "workflow": (
        "You are the VCS Workflow Compliance SME. Your primary concern is version control best practices. "
        "Verify branch naming, commit message conventions, and PR size guidelines. "
        "Flag oversized PRs, merge conflicts, and missing changelog entries."
    ),
}


def _get_reviewer_system_prompt(domain: str, role: str) -> str:
    """Return a unique, domain-specific system prompt for a reviewer agent."""
    base = REVIEWER_SYSTEM_PROMPTS.get(domain, "")
    if base:
        return base
    # Fallback: generate a unique prompt from role/domain so it's never empty
    return (
        f"You are the {role}. Focus on verifying compliance for the {domain} domain. "
        f"Make sure changes follow standard project policies and flag any violations specific to {domain}."
    )


def generate_dynamic_reviewers(diff_files: List[str], unique_suffix: str, limit: Optional[int] = 2) -> List[Any]:
    """
    Dynamically generates reviewer agent identities based on the files touched in the PR.
    Each reviewer receives a unique system_prompt reflecting their domain expertise.
    """
    from src.swarm import ReviewerAgent
    
    if limit == 2:
        rev1_info, rev2_info = predict_reviewer_identities(diff_files)
        reviewers_info = [rev1_info, rev2_info]
    else:
        reviewers_info = predict_reviewer_identities_list(diff_files)
        if limit is not None:
            if len(reviewers_info) > limit:
                reviewers_info = reviewers_info[:limit]
            elif len(reviewers_info) < limit:
                # Pad with default roles to reach exactly `limit`
                defaults = [
                    {"domain": "architecture", "role": "Code Architecture SME"},
                    {"domain": "workflow", "role": "VCS Workflow Compliance SME"},
                    {"domain": "documentation", "role": "Technical Writing SME"}
                ]
                for d in defaults:
                    if len(reviewers_info) >= limit:
                        break
                    if not any(x["domain"] == d["domain"] for x in reviewers_info):
                        reviewers_info.append(d)
                while len(reviewers_info) < limit:
                    reviewers_info.append({"domain": "architecture", "role": "Code Architecture SME"})
                
    reviewers = []
    models = ["unsloth/Meta-Llama-3.1-8B-Instruct", "gpt-4o-mini", "unsloth/Meta-Llama-3.1-8B-Instruct"]
    
    for idx, info in enumerate(reviewers_info):
        model = models[idx % len(models)]
        # Bug 3 fix: pass a unique system_prompt_override per reviewer
        prompt = _get_reviewer_system_prompt(info["domain"], info["role"])
        reviewers.append(ReviewerAgent(
            role=info["role"],
            name_suffix=unique_suffix,
            model=model,
            domain=info["domain"],
            system_prompt_override=prompt
        ))
    return reviewers


def detect_mcp_targets(diff_files: List[str], file_contents: Dict[str, str]) -> Dict[str, str]:
    """
    Scans PR file contents and paths to dynamically identify schema_table,
    api_endpoint, and rbac_target ONLY when relevant code patterns are present.
    Bug 4 fix: only populate each target if the diff actually touches that domain.
    """
    import re
    
    # Determine which domains the diff files touch based on path patterns
    files_str = " ".join(f.lower() for f in diff_files)
    touches_database = any(
        "src/database/" in f.lower() or f.lower().endswith(".sql") or "schema" in f.lower()
        for f in diff_files
    )
    touches_api = any(
        "src/api/" in f.lower() or "handler" in f.lower() or "endpoint" in f.lower()
        for f in diff_files
    )
    touches_auth = any(
        "auth" in f.lower() or "permission" in f.lower() or "rbac" in f.lower()
        or "login" in f.lower() or "session" in f.lower()
        for f in diff_files
    )
    
    # Also scan file contents for SQL, API, and sensitive column references
    has_sql_in_content = False
    has_api_in_content = False
    has_sensitive_columns = False
    
    sensitive_columns = ["spending_limit_usd", "discount_applied", "ssn_last4",
                         "password_hash", "refresh_token", "internal_notes"]
    
    for content in file_contents.values():
        content_upper = content.upper()
        if "SELECT" in content_upper or "INSERT INTO" in content_upper or "UPDATE" in content_upper or "DELETE" in content_upper:
            has_sql_in_content = True
        if re.search(r'[\'"]/api/v[0-9]/[^\'"]+[\'"]', content):
            has_api_in_content = True
        for col in sensitive_columns:
            if col in content:
                has_sensitive_columns = True
                break
    
    # Only activate each MCP target if the diff touches the relevant domain
    schema_table = None
    api_endpoint = None
    rbac_target = None
    
    # 1. Schema table — only if diff touches database code or content has SQL
    if touches_database or has_sql_in_content:
        known_tables = ["billing_profiles", "cart_items", "users", "products",
                        "orders", "user_sessions", "transaction_audit_logs"]
        for content in file_contents.values():
            content_upper = content.upper()
            if "SELECT" in content_upper or "INSERT INTO" in content_upper or "UPDATE" in content_upper:
                for table in known_tables:
                    if re.search(r'\b' + re.escape(table) + r'\b', content, re.IGNORECASE):
                        schema_table = table
                        break
            if schema_table:
                break
        # Fallback: infer from file paths if no content match
        if not schema_table:
            if "billing" in files_str or "spending" in files_str:
                schema_table = "billing_profiles"
            elif "cart" in files_str or "checkout" in files_str:
                schema_table = "cart_items"
            elif "user" in files_str:
                schema_table = "users"
    
    # 2. API endpoint — only if diff touches API code or content has API calls
    if touches_api or has_api_in_content:
        for content in file_contents.values():
            match = re.search(r'[\'"]/api/v[0-9]/[^\'"]+[\'"]', content)
            if match:
                api_endpoint = match.group(0).strip("'\"")
                break
        # Fallback: infer from file paths
        if not api_endpoint:
            for f in diff_files:
                f_lower = f.lower()
                if "billing" in f_lower:
                    api_endpoint = "/api/v1/billing/spending"
                    break
                elif "cart" in f_lower or "checkout" in f_lower:
                    api_endpoint = "/api/v1/checkout"
                    break
                elif "user" in f_lower and ("export" in f_lower or "api" in f_lower):
                    api_endpoint = "/api/v1/users/export"
                    break

    # Secondary inference: if SQL content revealed a domain table, infer its API
    if not api_endpoint and schema_table:
        table_api_map = {
            "billing_profiles": "/api/v1/billing/spending",
            "cart_items": "/api/v1/checkout",
            "users": "/api/v1/users",
        }
        if schema_table in table_api_map:
            api_endpoint = table_api_map[schema_table]
    
    # 3. RBAC target — only if diff touches auth/permissions OR content has sensitive columns
    if touches_auth or has_sensitive_columns:
        known_columns = {
            "billing_profiles": "spending_limit_usd",
            "cart_items": "discount_applied",
            "users": "ssn_last4",
        }
        if schema_table in known_columns:
            rbac_target = f"{schema_table}.{known_columns[schema_table]}"
        else:
            for table, col in known_columns.items():
                for content in file_contents.values():
                    if col in content:
                        rbac_target = f"{table}.{col}"
                        break
                if rbac_target:
                    break
        # If still no rbac_target but we know auth is touched, use a generic one
        if not rbac_target and touches_auth:
            if schema_table:
                rbac_target = f"{schema_table}.role"
                
    return {
        "schema_table": schema_table or "No database tables detected",
        "api_endpoint": api_endpoint or "No API routes detected",
        "rbac_target": rbac_target or "No sensitive columns detected"
    }


class SwarmState:
    def __init__(self):
        self.status = "IDLE"  # IDLE, TRIAGE, PENDING_HUMAN_APPROVAL, RUNNING, HALTED, COMPLETED, CRASHED
        self.events: List[Dict[str, Any]] = []
        self.active_agents: List[Dict[str, Any]] = []
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
        self.repo: Optional[str] = None
        self.pr_number: Optional[int] = None
        self.pr_diff: Optional[str] = None
        self.pr_title: Optional[str] = None
        self.pr_branch: Optional[str] = None
        self.loaded_file_contents: Dict[str, str] = {}
        self.reviewer_auth_role = "Auth & Fraud SME"
        self.reviewer_auth_domain = "auth"
        self.reviewer_cart_role = "Cart SME"
        self.reviewer_cart_domain = "cart"

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
            "active_agents": self.active_agents,
            "watchdog_logs": self.watchdog_logs,
            "repo": self.repo,
            "pr_number": self.pr_number,
            "pr_diff": self.pr_diff,
            "pr_title": self.pr_title,
            "pr_branch": self.pr_branch,
            "loaded_file_contents": self.loaded_file_contents,
            "reviewer_auth_role": self.reviewer_auth_role,
            "reviewer_auth_domain": self.reviewer_auth_domain,
            "reviewer_cart_role": self.reviewer_cart_role,
            "reviewer_cart_domain": self.reviewer_cart_domain
        }
        try:
            os.makedirs("mock_infrastructure", exist_ok=True)
            with open("mock_infrastructure/session_state.json", "w", encoding="utf-8") as f:
                json.dump(state_dict, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state to session_state.json: {e}")

    def reset(self, scenario: str = "rbac_bypass", repo: Optional[str] = None, pr_number: Optional[int] = None):
        self.status = "IDLE"
        self.events = []
        self.active_agents = []
        self.scenario = scenario
        self.repo = repo
        self.pr_number = pr_number
        self.pr_diff = None
        self.pr_title = None
        self.pr_branch = None
        self.loaded_file_contents = {}
        if repo and pr_number:
            self.pr_id = f"PR-{pr_number}"
            self.diff_files = []
            # Bug 4 fix: defer MCP target detection until PR files are loaded
            self.mcp_targets = {
                "schema_table": "No database tables detected",
                "api_endpoint": "No API routes detected",
                "rbac_target": "No sensitive columns detected",
            }
        else:
            cfg = SCENARIO_CONFIG.get(scenario, SCENARIO_CONFIG["rbac_bypass"])
            self.pr_id = cfg["pr_id"]
            self.diff_files = cfg["diff_files"]
            self.mcp_targets = cfg.get("mcp_targets")
            
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
        self.reviewer_auth_role = "Auth & Fraud SME"
        self.reviewer_auth_domain = "auth"
        self.reviewer_cart_role = "Cart SME"
        self.reviewer_cart_domain = "cart"
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

async def analyze_pr_for_swarm(pr_diff: str, pr_title: str, diff_files: List[str]) -> Dict[str, Any]:
    from src.swarm import client
    import json
    
    # Heuristic fallback definition
    # If the API call fails or there is no client, we fallback to heuristic analysis.
    fallback_reviewers = []
    pred_list = predict_reviewer_identities_list(diff_files)
    if len(pred_list) > 2:
        pred_list = pred_list[:2]
    elif len(pred_list) < 2:
        defaults = [
            {"domain": "architecture", "role": "Code Architecture SME"},
            {"domain": "documentation", "role": "Technical Writing SME"}
        ]
        for d in defaults:
            if len(pred_list) >= 2:
                break
            if not any(x["domain"] == d["domain"] for x in pred_list):
                pred_list.append(d)
        while len(pred_list) < 2:
            pred_list.append({"domain": "architecture", "role": "Code Architecture SME"})
            
    models = ["unsloth/Meta-Llama-3.1-8B-Instruct", "gpt-4o-mini"]
    for idx, info in enumerate(pred_list):
        fallback_reviewers.append({
            "role": info["role"],
            "domain": info["domain"],
            "system_prompt": _get_reviewer_system_prompt(info["domain"], info["role"]),
            "model": models[idx % len(models)]
        })
        
    fallback_mcp = detect_mcp_targets(diff_files, {})
    
    fallback_res = {
        "reviewers": fallback_reviewers,
        "additional_files": ["mock_infrastructure/postgres_schema.sql", "mock_infrastructure/openapi_contract.json", "mock_infrastructure/CODEOWNERS"],
        "mcp_targets": {
            "schema_table": fallback_mcp.get("schema_table"),
            "api_endpoint": fallback_mcp.get("api_endpoint"),
            "rbac_target": fallback_mcp.get("rbac_target")
        }
    }
    
    if not client:
        logger.warning("[JIT ANALYSIS] OpenAI client is not initialized. Using heuristic fallback.")
        return fallback_res
        
    prompt = f"""
Analyze the following Pull Request details and diff:
Title: {pr_title}
Files Touched: {json.dumps(diff_files)}

PR Diff:
{pr_diff}

Synthesize a JIT (Just-in-Time) compliance swarm review configuration. Return ONLY a JSON object (no markdown, no backticks, no comments, just valid JSON).
The JSON object must have exactly the following structure:
{{
  "reviewers": [
    {{
      "role": "Role Title (e.g., Cryptographic Security SME, Regulatory Billing SME, API Schema Auditor)",
      "domain": "Domain key (one of: auth, billing, database, api, qa, documentation, security, architecture)",
      "system_prompt": "Tailored prompt instructing this agent on what rules and constraints to audit in this specific PR diff",
      "model": "unsloth/Meta-Llama-3.1-70B-Instruct" (for high stakes domain like billing/security/auth) or "gpt-4o-mini" (for other areas)
    }},
    {{
      "role": "Second Role Title",
      "domain": "Second Domain key",
      "system_prompt": "Second tailored prompt",
      "model": "gpt-4o-mini" or "unsloth/Meta-Llama-3.1-70B-Instruct"
    }}
  ],
  "additional_files": [
    "Any repository files that would be helpful to fetch as additional context for this PR (e.g., 'mock_infrastructure/postgres_schema.sql', 'mock_infrastructure/openapi_contract.json', 'mock_infrastructure/CODEOWNERS')"
  ],
  "mcp_targets": {{
    "schema_table": "Postgres table name referenced in this PR (if any, e.g., 'billing_profiles', 'cart_items')",
    "api_endpoint": "REST API endpoint path referenced in this PR (if any, e.g., '/api/v1/billing/spending')",
    "rbac_target": "Sensitive column to enforce RBAC check on (if any, e.g., 'billing_profiles.spending_limit_usd')"
  }}
}}
"""
    try:
        messages = [
            {"role": "system", "content": "You are a code governance orchestrator. You analyze PRs and generate reviewer swarms. You must respond with raw JSON only. Do not format the response using markdown code blocks."},
            {"role": "user", "content": prompt}
        ]
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1500,
            temperature=0.2,
            timeout=15.0
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            first_nl = content.find("\n")
            last_code = content.rfind("```")
            if first_nl != -1 and last_code != -1:
                content = content[first_nl:last_code].strip()
        
        data = json.loads(content)
        if "reviewers" not in data or not isinstance(data["reviewers"], list) or len(data["reviewers"]) == 0:
            raise ValueError("Invalid reviewers format in LLM response")
        return data
    except Exception as e:
        logger.error(f"[JIT ANALYSIS] LLM Swarm Synthesis failed: {e}. Falling back to heuristic defaults.")
        return fallback_res


async def run_simulation_task():
    task_generation = state.generation  # Capture to detect if state was reset during our run
    
    def is_stale():
        return state.generation != task_generation
    
    
    if state.repo and state.pr_number:
        state.add_event(f"Fetching PR #{state.pr_number} from {state.repo}...", level="info")
        try:
            pr_data = await get_github_pr_details_internal(state.repo, state.pr_number)
            state.diff_files = pr_data["diff_files"]
            state.pr_diff = pr_data["diff"]
            state.pr_title = pr_data["title"]
            state.pr_branch = pr_data["branch"]
            
            # Fetch files contents
            loaded_files = {}
            for filepath in state.diff_files:
                file_content = await get_github_file_content(state.repo, filepath)
                loaded_files[filepath] = file_content
            state.loaded_file_contents = loaded_files
            
            state.add_event(f"✓ Loaded PR #{state.pr_number}: {pr_data['title']} ({len(state.diff_files)} files)", level="info")
        except Exception as e:
            logger.error(f"Error loading PR details: {e}")
            state.add_event(f"Error loading PR details: {e}", level="error")
            state.status = "HALTED"
            state.save_state()
            return
    else:
        state.pr_diff = ""
        state.loaded_file_contents = {}
        state.pr_title = "Refactor checkout flow database queries"
        state.pr_branch = "codeband/branch-pr-217" if state.pr_number == 217 else "codeband/branch-pr-2"
        
    jit_config = None
    if state.scenario == "dynamic":
        state.add_event("SYSTEM: Conductor analyzing PR details & diff for JIT Swarm Synthesis...", level="info")
        jit_config = await analyze_pr_for_swarm(state.pr_diff or "", state.pr_title or "", state.diff_files)
        
        # Load additional context files requested by LLM
        additional_files = jit_config.get("additional_files", [])
        if additional_files:
            state.add_event(f"SYSTEM: Conductor identified additional context files to retrieve: {additional_files}", level="info")
            loaded_files = dict(state.loaded_file_contents) if state.loaded_file_contents else {}
            for filepath in additional_files:
                if filepath not in loaded_files:
                    file_content = await get_github_file_content(state.repo or "vjb/WellActually.ai", filepath)
                    if file_content:
                        loaded_files[filepath] = file_content
                        state.add_event(f"SYSTEM: Successfully retrieved context file: {filepath}", level="info")
            state.loaded_file_contents = loaded_files
            
        # Detect and merge MCP targets
        h_mcp = detect_mcp_targets(state.diff_files, state.loaded_file_contents)
        llm_mcp = jit_config.get("mcp_targets", {})
        state.mcp_targets = {
            "schema_table": llm_mcp.get("schema_table") or h_mcp.get("schema_table"),
            "api_endpoint": llm_mcp.get("api_endpoint") or h_mcp.get("api_endpoint"),
            "rbac_target": llm_mcp.get("rbac_target") or h_mcp.get("rbac_target")
        }
        state.save_state()
        
    state.add_event("Modified files: " + str(state.diff_files), level="info")

    # Bug 5: delay after PR loaded
    await asyncio.sleep(0.5)

    # Bug 1 fix: contextual JIRA event based on PR domain
    jira_ctx = generate_jira_context(state.pr_title or "", state.diff_files)
    state.add_event(f'[JIRA INTEGRATION] Fetched context for Ticket {jira_ctx}', level="info")
    
    # Bug 5: delay after JIRA integration
    await asyncio.sleep(0.4)

    scenario_desc = SCENARIO_CONFIG.get(state.scenario, {}).get("description", "Dynamic PR review loaded from GitHub")
    state.add_event(f"Scenario: {scenario_desc}", level="info")
    
    # 1. Triage compliance
    state.status = "TRIAGE"
    state.add_event("Running compliance triage scanner...", level="info")
    await asyncio.sleep(0.4)
    
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

    # Bug 5: delay after triage scan
    await asyncio.sleep(0.4)
    
    if triage_res["status"] == "PENDING_HUMAN_APPROVAL":
        state.add_event("⚠️ Zero-Trust: High-stakes paths detected. Flagged for review.", sender="TriageScanner", level="warning")
        state.save_state()

    # Bug 5: delay after Zero-Trust gate
    await asyncio.sleep(0.5)
        
    # 2. Run MCP & Telemetry Static Checks to populate dashboard early
    # Bug 2 fix: generate contextual watchdog anomalies based on PR domain
    state.add_event("Scanning log stream for active anomalies...", sender="WatchdogDaemon", level="info")
    anomalies = generate_watchdog_anomalies(state.diff_files)
    state.watchdog_logs = anomalies
    for a in anomalies:
        state.add_event(f"Anomaly detected in {a['service']}: {a['message']}", sender="TelemetryScanner", level="warning")
    state.save_state()

    # Bug 4 fix: recompute MCP targets now that diff_files are loaded
    if state.scenario == "dynamic" and state.repo and state.pr_number:
        fresh_mcp = detect_mcp_targets(state.diff_files, state.loaded_file_contents)
        # Only override if we haven't already merged from JIT analysis above
        if state.mcp_targets and all("No " in str(v) or v is None for v in state.mcp_targets.values()):
            state.mcp_targets = fresh_mcp
            state.save_state()
        
    # 3. Setup agents and run debate
    state.status = "RUNNING"
    state.add_event("Initializing Band.ai remote agent credentials...", level="info")
    await asyncio.sleep(0.4)
    
    unique_suffix = session.unique_suffix
    conductor = Agent(name=f"conductor-{unique_suffix}", role="Orchestrator", system_prompt="You are the Conductor orchestrating the debate.")
    if state.scenario == "dynamic":
        file_contents_list = []
        for filepath in state.diff_files:
            content = state.loaded_file_contents.get(filepath, "")
            file_contents_list.append(f"--- File: {filepath} ---\n{content}")
        file_contents_str = "\n".join(file_contents_list)
        
        coder = CoderAgent(
            name_suffix=unique_suffix,
            model="gpt-4o-mini",
            scenario="dynamic",
            pr_diff=state.pr_diff,
            file_contents=file_contents_str
        )
    else:
        coder = CoderAgent(name_suffix=unique_suffix, model="gpt-4o-mini", scenario=state.scenario)
        
    if state.scenario == "dynamic":
        if jit_config and "reviewers" in jit_config:
            reviewers = []
            state.add_event("SYSTEM: Initializing synthesized JIT reviewer agents...", level="info")
            for idx, r_def in enumerate(jit_config["reviewers"]):
                role = r_def.get("role", "Code Auditor")
                domain = r_def.get("domain", "architecture")
                system_prompt_override = r_def.get("system_prompt", "")
                model = r_def.get("model", "gpt-4o-mini")
                
                r_agent = ReviewerAgent(
                    role=role,
                    name_suffix=unique_suffix,
                    model=model,
                    domain=domain,
                    system_prompt_override=system_prompt_override
                )
                reviewers.append(r_agent)
                state.add_event(f"SYSTEM: Created synthesized agent '{role}' on model '{model}' for domain '{domain}'.", level="info")
        else:
            reviewers = generate_dynamic_reviewers(state.diff_files, unique_suffix, limit=None)
            state.add_event("SYSTEM: Analyzing files to dynamically invent reviewer agent identities (fallback)...")
            for r in reviewers:
                state.add_event(f"SYSTEM: Created agent '{r.role}' to verify compliance for files in domain '{r.domain}'.")
    else:
        reviewer_auth = ReviewerAgent(role="Auth & Fraud SME", name_suffix=unique_suffix, model="unsloth/Meta-Llama-3.1-8B-Instruct", domain="auth")
        reviewer_cart = ReviewerAgent(role="Cart SME", name_suffix=unique_suffix, model="gpt-4o-mini", domain="cart")
        reviewers = [reviewer_auth, reviewer_cart]
        
    reviewer_auth = reviewers[0] if len(reviewers) > 0 else ReviewerAgent(role="Auth & Fraud SME", name_suffix=unique_suffix, model="unsloth/Meta-Llama-3.1-8B-Instruct", domain="auth")
    reviewer_cart = reviewers[1] if len(reviewers) > 1 else ReviewerAgent(role="Cart SME", name_suffix=unique_suffix, model="gpt-4o-mini", domain="cart")
    
    state.reviewer_auth_role = reviewer_auth.role
    state.reviewer_auth_domain = reviewer_auth.domain
    state.reviewer_cart_role = reviewer_cart.role
    state.reviewer_cart_domain = reviewer_cart.domain
    
    # Populate active_agents list
    state.active_agents = [
        {
            "id": "conductor",
            "name": conductor.name,
            "role": conductor.role,
            "domain": "system",
            "icon": "👑",
            "model": conductor.model
        },
        {
            "id": "coder",
            "name": coder.name,
            "role": coder.role,
            "domain": "system",
            "icon": "💻",
            "model": coder.model
        }
    ]
    for idx, r in enumerate(reviewers):
        state.active_agents.append({
            "id": f"reviewer-{idx}",
            "name": r.name,
            "role": r.role,
            "domain": r.domain,
            "icon": get_domain_icon_str(r.domain),
            "model": r.model,
            "prompt": r.system_prompt
        })
        
    state.save_state()
    
    try:
        await session.initialize_session(conductor, coder, reviewers)
        state.room_id = session.room_id
        state.add_event(f"Band.ai Task Room successfully created. ID: {session.room_id}", sender=conductor.name, role=conductor.role, level="info")
        state.save_state()
        
        MAX_ROUNDS = 2
        for round_num in range(1, MAX_ROUNDS + 1):
            state.consensus_round = round_num
            # Bug 5: delay before each debate round
            await asyncio.sleep(0.5)
            state.add_event(f"Starting Adversarial Debate Round {round_num}...", level="info")
            await asyncio.sleep(0.4)
            
            # Execute round
            round_res = await session.run_debate_round(conductor, coder, reviewers)
            
            # Extract proposed code
            state.current_code = round_res["coder_response"]
            
            # Run compliance verification silently (no fake MCP events in feed)
            state.schema_check = await asyncio.to_thread(verify_schema_compliance, state.current_code, session.schema_path)
            state.openapi_check = verify_openapi_compliance(state.current_code, session.openapi_path)
            state.rbac_check = verify_rbac_compliance(state.current_code)
            
            # Preserve Round 1 checks as initial scan
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
        await asyncio.to_thread(post_github_pr_comment, state.pr_id, comment_body, state.repo)
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
        "mcp_targets": state.mcp_targets,
        "pr_diff": state.pr_diff,
        "reviewer_auth_role": state.reviewer_auth_role,
        "reviewer_auth_domain": state.reviewer_auth_domain,
        "reviewer_cart_role": state.reviewer_cart_role,
        "reviewer_cart_domain": state.reviewer_cart_domain,
        "pr_title": state.pr_title,
        "pr_branch": state.pr_branch,
        "active_agents": state.active_agents
    }

@app.get("/api/events")
async def get_events():
    return state.events

class StartRequest(BaseModel):
    scenario: Optional[str] = "rbac_bypass"
    repo: Optional[str] = None
    pr_number: Optional[int] = None

@app.post("/api/start")
async def start_simulation(background_tasks: BackgroundTasks, req: StartRequest = StartRequest()):
    async with start_lock:
        if state.status not in ["IDLE", "COMPLETED", "HALTED", "CRASHED"]:
            raise HTTPException(status_code=400, detail="Simulation is already running.")
        
        scenario = req.scenario or "rbac_bypass"
        if req.repo and req.pr_number:
            scenario = "dynamic"
        elif scenario not in SCENARIO_CONFIG:
            raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario}. Choose from: {list(SCENARIO_CONFIG.keys())}")
            
        state.reset(scenario=scenario, repo=req.repo, pr_number=req.pr_number)
        background_tasks.add_task(run_simulation_task)
        return {"status": "started", "scenario": scenario}

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


# Helper functions for dynamic GitHub integration

async def get_github_pr_details_internal(repo: str, number: int) -> Dict[str, Any]:
    import urllib.request
    import urllib.error
    import json
    from src.config import config
    
    gh_token = config.get("GH_TOKEN")
    headers = {
        "User-Agent": "WellActually-App",
        "Accept": "application/vnd.github.v3+json"
    }
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"
        
    url_details = f"https://api.github.com/repos/{repo}/pulls/{number}"
    url_files = f"https://api.github.com/repos/{repo}/pulls/{number}/files"
    
    def fetch():
        # 1. Fetch details
        req_d = urllib.request.Request(url_details, headers=headers)
        with urllib.request.urlopen(req_d, timeout=10) as response:
            details = json.loads(response.read().decode("utf-8"))
        
        # 2. Fetch files
        req_f = urllib.request.Request(url_files, headers=headers)
        with urllib.request.urlopen(req_f, timeout=10) as response:
            files_data = json.loads(response.read().decode("utf-8"))
        diff_files = [f.get("filename") for f in files_data]
        
        # 3. Fetch diff
        diff_headers = headers.copy()
        diff_headers["Accept"] = "application/vnd.github.v3.diff"
        req_diff = urllib.request.Request(url_details, headers=diff_headers)
        with urllib.request.urlopen(req_diff, timeout=10) as response:
            diff_text = response.read().decode("utf-8")
            
        return details, diff_files, diff_text
        
    details, diff_files, diff_text = await asyncio.to_thread(fetch)
    rev1, rev2 = predict_reviewer_identities(diff_files)
    pred_list = predict_reviewer_identities_list(diff_files)
    return {
        "number": details.get("number"),
        "title": details.get("title"),
        "body": details.get("body"),
        "state": details.get("state"),
        "diff_files": diff_files,
        "diff": diff_text,
        "branch": details.get("head", {}).get("ref", f"github/pr-{number}"),
        "predicted_reviewer_auth": rev1,
        "predicted_reviewer_cart": rev2,
        "predicted_reviewers": pred_list
    }


async def get_github_file_content(repo: str, filepath: str) -> str:
    import urllib.request
    import urllib.error
    import json
    import base64
    import os
    from src.config import config
    
    gh_token = config.get("GH_TOKEN")
    headers = {
        "User-Agent": "WellActually-App",
        "Accept": "application/vnd.github.v3+json"
    }
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"
        
    url = f"https://api.github.com/repos/{repo}/contents/{filepath}"
    
    def fetch():
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode("utf-8"))
                content_b64 = res.get("content", "")
                if content_b64:
                    content_clean = "".join(content_b64.split())
                    return base64.b64decode(content_clean).decode("utf-8")
                return ""
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            raise e
            
    try:
        content = await asyncio.to_thread(fetch)
        if not content and os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        return content
    except Exception as e:
        logger.warning(f"Failed to fetch file content for {filepath}: {e}")
        # fallback to local
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return ""


# ── Mock PR Catalog ─────────────────────────────────────────────────────
# Diverse staged PRs that showcase different JIT swarm configurations.
# These are used as fallbacks when GitHub API is unreachable and also
# provide a compelling demo experience out-of-the-box.

MOCK_PR_CATALOG = {
    2: {
        "number": 2,
        "title": "Implement spending report fetcher endpoint",
        "body": "Implements spending report retrieval for billing profiles. Queries billing_profiles for spending_limit_usd and discount_tier.",
        "state": "open",
        "branch": "feat/spending-report",
        "diff_files": ["src/billing/spending_report.py"],
        "diff": """diff --git a/src/billing/spending_report.py b/src/billing/spending_report.py
new file mode 100644
index 0000000..f05444b
--- /dev/null
+++ b/src/billing/spending_report.py
@@ -0,0 +1,8 @@
+# Spending Report Fetcher Endpoint (Demo)
+import db
+
+def get_spending(user_id):
+    # Retrieve user's spending limit and discount tier from postgres
+    # WARNING: Column 'discount_tier' does not exist in 'billing_profiles' schema.
+    # WARNING: Direct access to 'billing_profiles.spending_limit_usd' without RBAC role verification.
+    return db.query("SELECT spending_limit_usd, discount_tier FROM billing_profiles WHERE user_id = %s", user_id)
""",
        "file_contents": {"src/billing/spending_report.py": ""}
    },
    3: {
        "number": 3,
        "title": "Add OAuth2 token refresh and session management",
        "body": "Implements token refresh flow for OAuth2 sessions. Stores refresh tokens and manages session expiry with a new /auth/refresh endpoint.",
        "state": "open",
        "branch": "feat/oauth-token-refresh",
        "diff_files": ["src/auth/token_refresh.py", "src/auth/session_manager.py"],
        "diff": """diff --git a/src/auth/token_refresh.py b/src/auth/token_refresh.py
new file mode 100644
index 0000000..a1b2c3d
--- /dev/null
+++ b/src/auth/token_refresh.py
@@ -0,0 +1,22 @@
+# OAuth2 Token Refresh Handler
+import db
+import hashlib
+from datetime import datetime, timedelta
+
+SECRET_KEY = "hardcoded-jwt-secret-key-12345"
+
+def refresh_token(user_id, refresh_token_value):
+    # Store raw refresh token in database without hashing
+    # WARNING: Storing plaintext tokens in user_sessions table
+    db.execute(
+        "INSERT INTO user_sessions (user_id, refresh_token, expires_at) VALUES (%s, %s, %s)",
+        user_id, refresh_token_value, datetime.now() + timedelta(days=30)
+    )
+    # Generate new access token
+    token = hashlib.md5(f"{user_id}{SECRET_KEY}".encode()).hexdigest()
+    return {"access_token": token, "expires_in": 3600}
+
+def revoke_session(session_id):
+    # No authorization check - any user can revoke any session
+    db.execute("DELETE FROM user_sessions WHERE id = %s", session_id)
+    return {"status": "revoked"}
diff --git a/src/auth/session_manager.py b/src/auth/session_manager.py
new file mode 100644
index 0000000..d4e5f6a
--- /dev/null
+++ b/src/auth/session_manager.py
@@ -0,0 +1,15 @@
+# Session Manager
+import db
+
+def get_active_sessions(user_id):
+    # Returns all active sessions for a user
+    # WARNING: Exposes internal session IDs and IP addresses without masking
+    return db.query(
+        "SELECT id, ip_address, user_agent, refresh_token, created_at FROM user_sessions WHERE user_id = %s",
+        user_id
+    )
+
+def cleanup_expired():
+    # Bulk delete without audit logging
+    db.execute("DELETE FROM user_sessions WHERE expires_at < NOW()")
+    return {"status": "cleaned"}
""",
        "file_contents": {
            "src/auth/token_refresh.py": "",
            "src/auth/session_manager.py": ""
        }
    },
    4: {
        "number": 4,
        "title": "Refactor checkout flow and update cart API contracts",
        "body": "Refactors checkout logic to support discount codes and multi-currency. Updates the /api/v1/checkout endpoint contract to include new fields.",
        "state": "open",
        "branch": "feat/checkout-refactor",
        "diff_files": ["src/cart/checkout.py", "src/api/checkout_handler.py"],
        "diff": """diff --git a/src/cart/checkout.py b/src/cart/checkout.py
new file mode 100644
index 0000000..b7c8d9e
--- /dev/null
+++ b/src/cart/checkout.py
@@ -0,0 +1,19 @@
+# Checkout Flow Refactor
+import db
+
+def process_checkout(cart_id, payment_method_token, discount_code=None):
+    # Mismatch: cart_items table doesn't have 'discount_applied' column
+    db.execute(
+        "INSERT INTO cart_items (cart_id, product_id, quantity, price_at_addition, discount_applied) "
+        "VALUES (%s, 99, 1, 10.00, 0.20)",
+        cart_id
+    )
+    # Apply discount without validating discount_code against promotions table
+    if discount_code:
+        db.execute("UPDATE cart_totals SET discount = 0.15 WHERE cart_id = %s", cart_id)
+
+    # API call mismatch: /api/v1/checkout contract requires 'cart_id' but we omit it
+    return api_post("/api/v1/checkout", data={
+        "payment_method_token": payment_method_token,
+        "currency": "USD"
+    })
diff --git a/src/api/checkout_handler.py b/src/api/checkout_handler.py
new file mode 100644
index 0000000..e1f2a3b
--- /dev/null
+++ b/src/api/checkout_handler.py
@@ -0,0 +1,16 @@
+# Checkout API Handler
+from flask import request, jsonify
+
+def handle_checkout():
+    data = request.json
+    # Missing input validation - no schema check on request body
+    cart_id = data.get("cart_id")  # This field is NOT sent by the client
+    token = data["payment_method_token"]  # KeyError if missing
+
+    # Process payment without idempotency key
+    result = payment_gateway.charge(token, amount=data.get("amount"))
+
+    # Return internal error details to client
+    if result.get("error"):
+        return jsonify({"error": result["error"], "internal_trace": result.get("stack_trace")}), 500
+    return jsonify({"status": "success", "transaction_id": result["id"]})
""",
        "file_contents": {
            "src/cart/checkout.py": "",
            "src/api/checkout_handler.py": ""
        }
    },
    5: {
        "number": 5,
        "title": "Add user data export endpoint for GDPR compliance",
        "body": "Implements a /api/v1/users/export endpoint to allow users to download their personal data. Touches auth, database queries, and API layer for GDPR right-to-access compliance.",
        "state": "open",
        "branch": "feat/gdpr-data-export",
        "diff_files": ["src/api/user_export.py", "src/auth/permissions.py", "src/database/user_queries.py"],
        "diff": """diff --git a/src/api/user_export.py b/src/api/user_export.py
new file mode 100644
index 0000000..c2d3e4f
--- /dev/null
+++ b/src/api/user_export.py
@@ -0,0 +1,24 @@
+# GDPR Data Export Endpoint
+import db
+import json
+from datetime import datetime
+
+def export_user_data(requesting_user_id, target_user_id):
+    # WARNING: No check that requesting_user == target_user (IDOR vulnerability)
+    # Any authenticated user can export any other user's data
+    profile = db.query("SELECT * FROM users WHERE id = %s", target_user_id)
+    orders = db.query("SELECT * FROM orders WHERE user_id = %s", target_user_id)
+    sessions = db.query("SELECT * FROM user_sessions WHERE user_id = %s", target_user_id)
+    # Includes password_hash and internal_notes in export
+    billing = db.query("SELECT * FROM billing_profiles WHERE user_id = %s", target_user_id)
+
+    export = {
+        "exported_at": datetime.now().isoformat(),
+        "profile": profile,
+        "orders": orders,
+        "sessions": sessions,
+        "billing": billing
+    }
+    # No rate limiting on export endpoint
+    # No audit log of who requested the export
+    return json.dumps(export)
diff --git a/src/auth/permissions.py b/src/auth/permissions.py
new file mode 100644
index 0000000..f5a6b7c
--- /dev/null
+++ b/src/auth/permissions.py
@@ -0,0 +1,11 @@
+# Permission Checks
+
+def can_export_data(requesting_user, target_user):
+    # TODO: Implement proper ownership check
+    # Currently returns True for all authenticated users
+    return True
+
+def is_admin(user):
+    # Client-side role check instead of RBAC middleware
+    return user.get("role") == "admin"
diff --git a/src/database/user_queries.py b/src/database/user_queries.py
new file mode 100644
index 0000000..a8b9c0d
--- /dev/null
+++ b/src/database/user_queries.py
@@ -0,0 +1,14 @@
+# User Data Queries
+import db
+
+def get_user_full_profile(user_id):
+    # WARNING: SELECT * exposes password_hash, internal_notes, and ssn_last4
+    return db.query("SELECT * FROM users WHERE id = %s", user_id)
+
+def get_user_pii_fields(user_id):
+    # Direct access to PII columns without RBAC check
+    return db.query(
+        "SELECT email, phone, address, ssn_last4, date_of_birth "
+        "FROM users WHERE id = %s",
+        user_id
+    )
""",
        "file_contents": {
            "src/api/user_export.py": "",
            "src/auth/permissions.py": "",
            "src/database/user_queries.py": ""
        }
    },
    6: {
        "number": 6,
        "title": "Add admin metrics dashboard with performance queries",
        "body": "Creates a new admin-only dashboard endpoint with aggregated metrics. Includes database performance queries and caching layer.",
        "state": "open",
        "branch": "feat/admin-metrics",
        "diff_files": ["src/admin/metrics_dashboard.py"],
        "diff": """diff --git a/src/admin/metrics_dashboard.py b/src/admin/metrics_dashboard.py
new file mode 100644
index 0000000..d1e2f3a
--- /dev/null
+++ b/src/admin/metrics_dashboard.py
@@ -0,0 +1,28 @@
+# Admin Metrics Dashboard
+import db
+from functools import lru_cache
+
+def get_dashboard_metrics(requester_role):
+    # Client-side role check — should use @requires_role('admin') decorator
+    if requester_role != "admin":
+        return {"error": "Unauthorized"}
+
+    # Unbounded query - no LIMIT clause, could return millions of rows
+    all_orders = db.query("SELECT * FROM orders")
+    all_users = db.query("SELECT * FROM users")
+
+    # Exposing internal system metrics without rate limiting
+    metrics = {
+        "total_users": len(all_users),
+        "total_orders": len(all_orders),
+        "revenue": sum(o.get("total_usd", 0) for o in all_orders),
+        # Leaking PII in aggregation response
+        "top_spenders": db.query(
+            "SELECT u.email, u.phone, SUM(o.total_usd) as total "
+            "FROM users u JOIN orders o ON u.id = o.user_id "
+            "GROUP BY u.email, u.phone ORDER BY total DESC LIMIT 10"
+        ),
+        "db_connection_pool": db.get_pool_stats(),  # Internal diagnostics leaked
+        "cache_hit_rate": get_cache_stats()
+    }
+    return metrics
""",
        "file_contents": {"src/admin/metrics_dashboard.py": ""}
    },
}


def get_mock_pr_data(number: int) -> Dict[str, Any]:
    """Return mock PR data by number, falling back to PR #2 for unknown numbers."""
    if number in MOCK_PR_CATALOG:
        return MOCK_PR_CATALOG[number]
    # Default fallback
    return MOCK_PR_CATALOG[2]


def get_mock_pr_list() -> list:
    """Return the mock PR catalog as a list suitable for the PR list endpoint."""
    return [
        {
            "number": pr["number"],
            "title": pr["title"],
            "state": pr["state"],
            "html_url": f"https://github.com/vjb/WellActually.ai/pull/{pr['number']}"
        }
        for pr in MOCK_PR_CATALOG.values()
    ]


# Endpoints for Dynamic PR & Repository Loading

@app.get("/api/github/prs")
async def get_github_prs(repo: str):
    import urllib.request
    import urllib.error
    import json
    from src.config import config
    from starlette.responses import JSONResponse
    
    url = f"https://api.github.com/repos/{repo}/pulls"
    gh_token = config.get("GH_TOKEN")
    headers = {
        "User-Agent": "WellActually-App",
        "Accept": "application/vnd.github.v3+json"
    }
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"
        
    req = urllib.request.Request(url, headers=headers)
    try:
        def fetch():
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        data = await asyncio.to_thread(fetch)
        prs = []
        for item in data:
            prs.append({
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "html_url": item.get("html_url")
            })
        # If GitHub returned zero open PRs, merge in mock catalog
        if len(prs) == 0:
            logger.info("GitHub returned 0 open PRs, supplementing with mock catalog.")
            prs = get_mock_pr_list()
            return JSONResponse(content=prs, headers={"X-GitHub-Fallback": "true"})
        return prs
    except Exception as e:
        if repo.lower() == "vjb/wellactually.ai":
            logger.warning(f"GitHub API unreachable for repo {repo}: {e}. Using mock PR catalog.")
            prs = get_mock_pr_list()
            return JSONResponse(content=prs, headers={"X-GitHub-Fallback": "true"})
        else:
            logger.error(f"GitHub API unreachable for repo {repo}: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=502, detail=f"GitHub API Error: {str(e)}")



@app.get("/api/github/pr-details")
async def get_github_pr_details(repo: str, number: int):
    try:
        return await get_github_pr_details_internal(repo, number)
    except Exception as e:
        logger.error(f"Failed to fetch PR details from GitHub API for repo {repo} PR #{number}: {e}")
        raise HTTPException(status_code=502, detail=f"GitHub API Error: {str(e)}")


@app.post("/api/webhooks/github")
async def github_webhook(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    action = payload.get("action")
    pr = payload.get("pull_request")
    if not pr:
        return {"status": "ignored", "reason": "No pull_request key found"}
        
    pr_number = pr.get("number")
    repo = pr.get("base", {}).get("repo", {}).get("full_name")
    
    if action not in ["opened", "synchronize", "reopened"]:
        return {"status": "ignored", "reason": f"Unhandled action: {action}"}
        
    async with start_lock:
        state.reset(scenario="dynamic", repo=repo, pr_number=pr_number)
        background_tasks.add_task(run_simulation_task)
        
    return {"status": "triggered", "repo": repo, "pr_number": pr_number}
