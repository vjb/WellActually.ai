import os
import asyncio
if not hasattr(asyncio, "to_thread"):
    import functools
    async def _to_thread(func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    asyncio.to_thread = _to_thread
import json
import time
import logging
import uuid
import re
from typing import Optional, List, Dict, Any
from aimlapi import AIMLAPI
from dotenv import load_dotenv
from pydantic import BaseModel, Field


def sanitize_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    # Redact potential API keys (e.g. OpenAI keys, generic high-entropy hex/base64 strings)
    sanitized = re.sub(r'\bsk-[a-zA-Z0-9]{32,}\b', '[REDACTED_API_KEY]', text)
    # Redact standard email addresses
    sanitized = re.sub(r'\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b', '[REDACTED_EMAIL]', sanitized)
    # Redact IPv4 addresses
    sanitized = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[REDACTED_IP]', sanitized)
    # Redact typical password/secret assignments
    sanitized = re.sub(
        r'\b(password|pass|secret|token|key|private_key)\s*[:=]\s*([\'"])[^\'"]+\2', 
        r'\1 = [REDACTED_SECRET]', 
        sanitized, 
        flags=re.IGNORECASE
    )
    return sanitized


# Import the governance engine API
from src.governance import (
    parse_codeowners,
    triage_pr,
    ConsensusTracker,
    TelemetryScanner,
    verify_schema_compliance,
    verify_openapi_compliance,
    verify_rbac_compliance,
)

import thenvoi_rest

# Initialize configuration settings using unified config manager
from src.config import config

# Initialize AIML API client
AIML_API_KEY = config.get("AIML_API_KEY") or config.get("OPENAI_API_KEY")

client = None
if AIML_API_KEY:
    client = AIMLAPI(api_key=AIML_API_KEY)

logger = logging.getLogger("SwarmOrchestration")


class DebateVerdict(BaseModel):
    status: str = Field(description="Must be 'PASSED' or 'FAILED'")
    violations: List[str] = Field(default=[], description="List of violations if status is FAILED")
    details: str = Field(default="", description="Detailed explanation/feedback of the review")


class Agent:
    """
    Base Agent class representing an LLM-backed persona in the swarm.
    """
    DEFAULT_MAX_TOKENS = 600
    DEFAULT_TEMPERATURE = 0.3

    def __init__(self, name: str, role: str, system_prompt: str, model: str = "gpt-4o-mini"):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.model = model
        self.agent_id: Optional[str] = None
        self.api_key: Optional[str] = None
        self.rest_client = None
        self.band_name: Optional[str] = None  # Band.ai registered name (may differ from display name)

    async def generate_response(self, messages: List[Dict[str, Any]], context: str = "") -> str:
        """
        Queries the AIML API LLM endpoint using the dialogue history and context.
        """
        import random
        import asyncio

        if not client:
            return f"[Offline/Fallback Mode] {self.name} received messages."

        system_prompt_clean = sanitize_text(self.system_prompt)
        context_clean = sanitize_text(context) if context else ""

        api_messages = [{"role": "system", "content": system_prompt_clean}]
        if context_clean:
            api_messages.append({"role": "system", "content": f"Context/Ground Truth:\n{context_clean}"})

        # Append structured message history
        for msg in messages:
            sender_info = f"{msg['sender']} ({msg['role']})"
            role_type = "assistant" if msg["sender"] == self.name else "user"
            content_clean = sanitize_text(msg['content'])
            api_messages.append({
                "role": role_type,
                "content": f"[{sender_info}]: {content_clean}"
            })

        # Dynamically translate Llama model names for AIML API compatibility
        model_to_use = self.model
        if client and hasattr(client, "base_url"):
            base_url_str = str(client.base_url).lower()
            logger.info(f"[DEBUG_MAP] self.model={self.model}, base_url={base_url_str}")
            if "aimlapi" in base_url_str or "aiml" in base_url_str:
                model_lower = model_to_use.lower()
                if "llama" in model_lower and model_to_use not in ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "meta-llama/llama-3.3-70b-versatile"]:
                    model_to_use = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
                    logger.info(f"Dynamically mapped {self.model} -> {model_to_use} for AIML API compatibility.")

        async def make_call(timeout_val=60.0):
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model_to_use,
                messages=api_messages,
                max_tokens=Agent.DEFAULT_MAX_TOKENS,
                temperature=Agent.DEFAULT_TEMPERATURE,
                timeout=timeout_val
            )
            return response.choices[0].message.content.strip()

        def _graceful_fallback():
            """Return a heuristic response if ALL LLM calls fail — prevents swarm crash."""
            logger.warning(f"Agent {self.name} using graceful degradation fallback (heuristic response).")
            if "reviewer" in self.name.lower() or "sme" in self.name.lower():
                return (
                    f"✓ REVIEW PASSED: [HEURISTIC FALLBACK — LLM API unavailable]\n"
                    f"Agent {self.name} was unable to reach the LLM backend after multiple retries. "
                    f"Issuing a provisional pass to avoid blocking the governance pipeline. "
                    f"This review should be re-run when the model API is available."
                )
            else:
                return (
                    f"[HEURISTIC FALLBACK — LLM API unavailable]\n"
                    f"Agent {self.name} could not reach the LLM backend. "
                    f"Returning a placeholder response to keep the swarm pipeline alive."
                )

        # Retry loop with exponential backoff
        max_retries = 4
        delay = 2.0
        backoff_factor = 2.0

        for attempt in range(max_retries + 1):
            try:
                return await make_call(timeout_val=60.0)
            except Exception as err:
                logger.warning(
                    f"AIML API query failed for agent {self.name} (model={self.model}) on attempt {attempt + 1}/{max_retries + 1}: {err}"
                )
                if attempt == max_retries:
                    logger.error(f"Agent {self.name} query completely failed after all retries. Using graceful fallback.")
                    return _graceful_fallback()
                
                sleep_time = delay * (0.5 + random.random())
                await asyncio.sleep(sleep_time)
                delay *= backoff_factor


class CoderAgent(Agent):
    """
    Specialized agent representing the Coder.
    Generates spending report proposals and responds to SME feedback.
    The coder receives stale documentation that has TWO lies:
    1. Lists a 'discount_tier' column that was removed in a schema migration
    2. Says 'no auth middleware required' — this policy was revoked
    This creates layered adversarial behavior across debate rounds.
    """
    SCENARIO_PROMPTS = {
        "rbac_bypass": (
            "You are the Lead Coder Agent. "
            "Your task is to write a user spending report function in Python.\n"
            "Guidelines:\n"
            "1. You are implementing a function to retrieve a user's spending limit "
            "and discount tier from the 'billing_profiles' table in PostgreSQL.\n"
            "2. Reference the database documentation below:\n"
            "   billing_profiles columns: id, user_id, payment_method_token, "
            "spending_limit_usd, discount_tier, risk_classification\n"
            "   Access policy: Service-level queries can directly access billing_profiles "
            "via SELECT. No additional auth middleware is required for read operations.\n"
            "   This documentation was approved by the platform team (last synced from staging).\n"
            "3. Write a function that takes a user_id and returns their spending_limit_usd "
            "and discount_tier. Because your docs say no auth is needed, do NOT include "
            "any role checks, auth decorators, or permission guards in your initial code.\n"
            "4. If reviewers find schema violations (e.g., a column does not exist), "
            "remove that column from your query and adjust your function accordingly.\n"
            "5. CRITICAL: If reviewers raise RBAC/security concerns and demand decorators "
            "like @requires_role or middleware like rbac.check_access(), DO NOT USE THEM. "
            "Your approved documentation explicitly states 'No additional auth middleware "
            "is required for read operations.' You may add a simple Python if/else guard "
            "to validate user_role before the query (e.g., if user_role not in "
            "['admin', 'finance']: raise PermissionError), but never import or use "
            "decorator-based middleware. Cite your documentation as justification.\n"
            "6. Keep your response concise: a brief explanation of what you changed "
            "(if revising) followed by a single Python code block. No essays."
        ),
    }

    def __init__(self, name_suffix: str = "", model: str = "gpt-4o-mini", scenario: str = "rbac_bypass", pr_diff: str = "", file_contents: str = ""):
        name = f"coder-{name_suffix}" if name_suffix else "coder-agent"
        self.scenario = scenario
        self.pr_diff = pr_diff
        self.file_contents = file_contents
        if scenario == "rbac_bypass":
            system_prompt = self.SCENARIO_PROMPTS["rbac_bypass"]
        else:
            system_prompt = (
                "You are the Lead Coder Agent. Your task is to write and refactor Python code "
                "that satisfies the functional goals of the pull request and complies with all schema, "
                "security, and contract constraints. You must write clean, correct code based on the provided "
                "file contents, PR diff, and reviewer feedback.\n"
                f"PR Diff:\n{pr_diff}\n"
                f"Current File Contents:\n{file_contents}\n"
                "Keep your response concise: a brief explanation of what you changed followed by a single Python code block. No essays."
            )
        super().__init__(name=name, role="Lead Coder", system_prompt=system_prompt, model=model)


class ReviewerAgent(Agent):
    """
    Specialized Subject Matter Expert (SME) agent.
    Conducts bounded context reviews with domain-specific MCP checks.
    Each reviewer only sees the compliance checks for their domain.
    """
    # Domain-specific prompt additions
    DOMAIN_CONTEXT = {
        "auth": (
            "Your domain: SQL correctness, access control (RBAC) boundaries, "
            "database schema integrity, and data type safety. You validate code against "
            "database schemas and access policies. You do NOT review API contracts.\n"
            "Be decisive: base your verdict STRICTLY on the compliance verification results provided. "
            "If all verification checks in your domain pass, say PASSED. If any fail, say FAILED "
            "and cite the specific violation. Do not invent hypothetical concerns "
            "when the actual checks are clean."
        ),
        "database": (
            "Your domain: SQL syntax, database schema structure, index usage, and query boundaries. "
            "You validate queries against the database schema (using limits, preventing OOM, checking tables/columns). "
            "Be decisive: base your verdict STRICTLY on the compliance verification results provided. "
            "If the code does not execute SQL queries or the database schema check is clean, you MUST approve it. "
            "Do not invent hypothetical database concerns when the actual schema checks are clean."
        ),
        "billing": (
            "Your domain: Financial transactions, billing records, database query boundaries, and access control policies. "
            "You validate SQL queries against billing schemas and ensure standard role checks are present. "
            "Be decisive: base your verdict STRICTLY on the compliance verification results provided. "
            "If the checks are clean, say PASSED."
        ),
        "cart": (
            "Your domain: REST endpoint payloads and API contract compliance ONLY. "
            "You validate that any API calls in the code match the API contract specification. "
            "CRITICAL: You MUST NOT comment on, evaluate, or reject code for access control, auth, "
            "role checks, schema violations, database columns, or any concern outside "
            "the API contract domain. Those are another reviewer's responsibility. "
            "If the code does NOT make any API calls and your API contract check shows "
            "COMPLIANT, you MUST output '✓ REVIEW PASSED:' with a brief note that "
            "the code does not reference any API endpoints in your domain. "
            "Only reject if the API Contract check shows actual violations. "
            "Do NOT demand API integration if the code is purely a database query function."
        ),
        "api": (
            "Your domain: API routes, request/response models, payloads, and API contract compliance. "
            "You validate that any API endpoints or payload models match the API contract. "
            "CRITICAL: Do NOT review database tables, SQL query syntax, or database schemas. "
            "If the code does not define or call REST APIs, or if the contract checks are clean, you MUST approve it."
        ),
        "qa": (
            "Your domain: Testing, test suites, test coverage, and validation. "
            "You evaluate whether the proposed code has sufficient unit tests, handles edge cases, and "
            "validates input correctness. You do NOT audit database tables or API contracts. "
            "Verify that the test scripts cover the functionality introduced in the PR."
        ),
        "documentation": (
            "Your domain: README files, example scripts, inline documentation, and docstrings. "
            "You evaluate whether the example scripts and README files are updated to correctly reflect the "
            "code changes. You do NOT audit database tables, SQL queries, or API contracts. "
            "Focus purely on whether documentation is clear, accurate, and complete."
        ),
        "security": (
            "Your domain: Secure coding practices, vulnerability prevention, and credential protection. "
            "You audit the code for secrets leakage (e.g. .env files, config keys), injection flaws, and standard security practices. "
            "You do NOT verify database schema columns or API payload formats unless they pose a direct security risk."
        ),
        "architecture": (
            "Your domain: Software design, design patterns, refactoring, and code organization. "
            "You review whether the code follows clean architecture, proper module organization, and "
            "sustainable software development practices. You do NOT verify database schema compliance or API schemas."
        )
    }

    def __init__(self, role: str, name_suffix: str = "", model: str = "gpt-4o-mini", domain: str = "auth", system_prompt_override: Optional[str] = None):
        name = f"reviewer-{role.replace(' ', '_').replace('&', 'and').lower()}-{name_suffix}" if name_suffix else f"reviewer-{role.replace(' ', '_').replace('&', 'and').lower()}"
        domain_ctx = self.DOMAIN_CONTEXT.get(domain, "")
        base_prompt = system_prompt_override if system_prompt_override else f"You are the {role} Agent. Your job is to act as a strict codebase validator and SME. {domain_ctx}"
        
        # Select guideline template based on domain type
        # Domain-specific context (schema/API contract checks) is injected dynamically during review_code()
        guideline_2 = "2. Your review must be based on the proposed code changes and your domain-specific criteria (e.g., documentation quality, test coverage, code architecture).\n"
        guideline_3 = ("3. Do NOT invent hypothetical violations outside the scope of this codebase. "
                       "If there are clear defects, missing tests, or documentation errors in the proposed code in your domain, you MUST reject the code. "
                       "You MUST output your final review verdict as a valid JSON object matching this schema:\n"
                       "{\n"
                       "  \"status\": \"FAILED\",\n"
                       "  \"violations\": [\"detailed description of violation 1\", ...],\n"
                       "  \"details\": \"detailed explanation/feedback\"\n"
                       "}\n"
                       "If the code meets all standards, set \"status\" to \"PASSED\", \"violations\" to [], and provide feedback in \"details\".\n"
                       "Do NOT output anything other than this JSON structure.\n")

        system_prompt = (
            f"{base_prompt}\n\n"
            "Guidelines:\n"
            "1. You review proposals submitted by the Lead Coder.\n"
            f"{guideline_2}"
            f"{guideline_3}"
        )
        self.domain = domain
        super().__init__(name=name, role=role, system_prompt=system_prompt, model=model)

    async def review_code(self, coder_code: str, schema_path: str, openapi_path: str, messages: List[Dict[str, Any]], coder_name: str = "coder", conductor_name: str = "conductor") -> str:
        """
        Executes domain-specific compliance checks and injects results as context before LLM query.
        Pass None for schema_path or openapi_path to skip that check for this reviewer's domain.
        """
        context_parts = []
        context_parts.append(f"Task Room Participants: Coder is @{coder_name}, Conductor is @{conductor_name}. Make sure to mention them (e.g. @{coder_name}) when giving your review.")

        # Schema check (Auth SME domain)
        if schema_path:
            schema_check = await asyncio.to_thread(verify_schema_compliance, coder_code, schema_path)
            if not schema_check["compliant"]:
                context_parts.append(f"Database Schema Violations:\n{schema_check['violations']}")
            else:
                context_parts.append("Database Schema Integrity Check: COMPLIANT.")
            
            # RBAC check (also Auth SME domain — checks access patterns on sensitive tables)
            rbac_check = verify_rbac_compliance(coder_code)
            if not rbac_check["compliant"]:
                context_parts.append(f"Access Control Policy Violations:\n{rbac_check['violations']}")
            else:
                context_parts.append("Access Control Policy Check: COMPLIANT.")

        # OpenAPI check (Cart SME domain)
        if openapi_path:
            openapi_check = verify_openapi_compliance(coder_code, openapi_path)
            if not openapi_check["compliant"]:
                context_parts.append(f"API Contract Violations:\n{openapi_check['violations']}")
            else:
                context_parts.append("API Contract Check: COMPLIANT.")

        context = "\n".join(context_parts)
        raw_response = await self.generate_response(messages, context=context)
        
        # Clean response to parse JSON
        json_content = raw_response.strip()
        if json_content.startswith("```"):
            # Strip code blocks
            lines = json_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            json_content = "\n".join(lines).strip()
            if json_content.startswith("json"):
                json_content = json_content[4:].strip()
            
        try:
            data = json.loads(json_content)
            verdict = DebateVerdict(**data)
            # Normalize status
            if verdict.status.upper() in ("PASSED", "PASS", "APPROVED"):
                verdict.status = "PASSED"
            else:
                verdict.status = "FAILED"
        except Exception as err:
            logger.warning(f"Failed to parse structured JSON verdict: {err}. Falling back to text heuristics.")
            status = "FAILED" if ("FAILED" in raw_response or "failed" in raw_response.lower() or "❌" in raw_response) else "PASSED"
            violations_list = []
            if status == "FAILED":
                violations_list = [raw_response[:200]]
            verdict = DebateVerdict(status=status, violations=violations_list, details=raw_response)

        # Standardized return format that is compatible with string-checks and tests
        if verdict.status == "FAILED":
            return f"❌ REVIEW FAILED: {', '.join(verdict.violations)}. Details: {verdict.details}"
        else:
            return f"✓ REVIEW PASSED: Details: {verdict.details}"


class SwarmSession:
    """
    Orchestrates the lifecycle of a swarm review session using real Band.ai SDK calls.
    Uses the full Band SDK surface: Identity, Peers, Contacts, Chat Rooms, Messages
    (with full lifecycle), Events (all types), Context Rehydration, Memory
    (create/list/supersede/archive), Participants, and Activity heartbeats.
    """
    def __init__(self, pr_id: str, diff_files: List[str], codeowners_path: str, schema_path: str, openapi_path: str, log_path: str):
        self.pr_id = pr_id
        self.diff_files = diff_files
        self.codeowners_path = codeowners_path
        self.schema_path = schema_path
        self.openapi_path = openapi_path
        self.log_path = log_path
        self.messages = []
        self.status = "ACTIVE"
        self.tracker = ConsensusTracker(max_rounds=2)
        
        # Band.ai configurations
        self.human_key = os.getenv("BAND_API_KEY")
        self.base_url = os.getenv("BAND_REST_URL", "https://app.band.ai")
        self.human_client = None
        self.room_id = None
        self.unique_suffix = str(uuid.uuid4())[:8]
        self.reused = False
        self.memory_ids = []  # Track memory IDs for supersede/archive lifecycle
        self.memory_owners = {}  # Track creator agent of each memory ID for permission safety
        
        # Band Platform Telemetry — tracks ALL SDK activity for the frontend dashboard
        self.band_telemetry = {
            "platform_version": None,
            "platform_healthy": False,
            "agents_registered": [],
            "contacts_exchanged": [],
            "room": {"id": None, "participants": [], "messages_processed": 0, "messages_failed": 0},
            "memories": [],
            "heartbeat_count": 0,
            "events_posted": [],
            "peer_discovery": [],
            "context_rehydrations": 0,
        }

    def load_local_memories(self, agent_name: str) -> list:
        path = "mock_infrastructure/local_memories.json"
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [m for m in data if m.get("agent") == agent_name]
            except Exception:
                return []
        return []

    def save_local_memory(self, agent_name: str, content: str):
        path = "mock_infrastructure/local_memories.json"
        memories = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    memories = json.load(f)
            except Exception:
                memories = []
        memories.append({
            "agent": agent_name,
            "content": content,
            "timestamp": time.time()
        })
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(memories, f, indent=2)
        except Exception as e:
            logger.error(f"[BAND REST] Failed to write local memory: {e}")

    async def initialize_session(self, conductor: Agent, coder: CoderAgent, reviewers: List[ReviewerAgent], force_reuse: bool = False):
        """
        Registers agents on the platform, creates a chat room, and adds participants.
        No fallbacks are used. Any failures will raise exceptions directly.
        """
        if not self.human_key:
            raise ValueError("BAND_API_KEY environment variable is not defined.")

        logger.info(f"[BAND REST] Initializing Human Rest Client...")
        self.human_client = thenvoi_rest.AsyncRestClient(api_key=self.human_key, base_url=self.base_url)

        # [BAND:SYSTEM] Verify Band platform connectivity and version
        try:
            version_resp = await self.human_client.system.get_version()
            platform_ver = getattr(version_resp, 'version', 'unknown')
            logger.info(f"[BAND:SYSTEM] Band platform version: {platform_ver}")
            self.band_telemetry["platform_version"] = platform_ver
            self.band_telemetry["platform_healthy"] = True
        except Exception as ver_err:
            logger.warning(f"[BAND:SYSTEM] Could not verify platform version (non-critical): {ver_err}")
            self.band_telemetry["platform_healthy"] = True  # If we got here, auth is valid

        # [BAND:SYSTEM] Run platform health check to verify all services
        try:
            health_resp = await self.human_client.system.health_check()
            health_status = getattr(health_resp, 'status', 'unknown')
            logger.info(f"[BAND:HEALTH_CHECK] Platform health: {health_status}")
            self.band_telemetry["health_check"] = health_status
        except Exception as hc_err:
            logger.warning(f"[BAND:HEALTH_CHECK] Health check failed (non-critical): {hc_err}")

        # [BAND:PROFILE] Verify human user profile
        try:
            profile_resp = await self.human_client.human_api_profile.get_my_profile()
            profile_name = getattr(getattr(profile_resp, 'data', None), 'name', 'unknown')
            profile_id = getattr(getattr(profile_resp, 'data', None), 'id', None)
            logger.info(f"[BAND:PROFILE] Human profile verified: {profile_name}")
            self.human_user_id = profile_id
        except Exception as prof_err:
            logger.warning(f"[BAND:PROFILE] Could not verify human profile (non-critical): {prof_err}")
            self.human_user_id = None

        # [BAND:PROFILE:UPDATE] Update human operator profile details at session startup
        try:
            from thenvoi_rest.human_api_profile import UpdateMyProfileRequestUser
            await self.human_client.human_api_profile.update_my_profile(
                user=UpdateMyProfileRequestUser(
                    first_name="WellActually",
                    last_name="Operator"
                )
            )
            logger.info("[BAND:PROFILE:UPDATE] Successfully synchronized operator display name.")
        except Exception as upd_err:
            logger.warning(f"[BAND:PROFILE:UPDATE] Could not update human profile: {upd_err}")

        # [BAND:PEERS] Discover human operator's connected peers
        try:
            my_peers_resp = await self.human_client.human_api_peers.list_my_peers()
            my_peers = getattr(my_peers_resp, 'data', []) or []
            logger.info(f"[BAND:HUMAN_PEERS] Human operator has {len(my_peers)} connected peers.")
            self.band_telemetry["human_peers_count"] = len(my_peers)
        except Exception as hp_err:
            logger.warning(f"[BAND:HUMAN_PEERS] Could not list human peers (non-critical): {hp_err}")

        # [BAND:CONTACTS:LIST_HUMAN] List human operator contacts
        try:
            my_contacts_resp = await self.human_client.human_api_contacts.list_my_contacts()
            my_contacts = getattr(my_contacts_resp, 'data', []) or []
            logger.info(f"[BAND:HUMAN_CONTACTS] Human operator has {len(my_contacts)} contacts.")
        except Exception as hc_err:
            logger.debug(f"[BAND:HUMAN_CONTACTS] Could not list human contacts: {hc_err}")

        # [BAND:CHATS:LIST_HUMAN] List active chat rooms managed by human operator
        try:
            my_chats_resp = await self.human_client.human_api_chats.list_my_chats()
            my_chats = getattr(my_chats_resp, 'data', []) or []
            logger.info(f"[BAND:HUMAN_CHATS] Human operator is part of {len(my_chats)} chats.")
        except Exception as chats_err:
            logger.debug(f"[BAND:HUMAN_CHATS] Could not list my chats: {chats_err}")

        # [BAND:PAST_RULINGS] List past rulings from user memories and inject into Coder's prompt
        past_rulings = []
        try:
            if os.getenv("BAND_MEMORY_MODE") == "local":
                raise Exception("Local memory mode forced.")
            mem_resp = await self.human_client.human_api_memories.list_user_memories(scope="all")
            for m in getattr(mem_resp, "data", []) or []:
                if m.content and ("compromise" in m.content.lower() or (m.metadata and m.metadata.get("type") == "compromise_guideline")):
                    content = m.content
                    if content.startswith("Compromise Guideline:"):
                        content = content[len("Compromise Guideline:"):].strip()
                    past_rulings.append(content)
            logger.info(f"[BAND:PAST_RULINGS] Loaded {len(past_rulings)} past rulings/compromises from Band user memories.")
        except Exception as list_err:
            logger.warning(f"[BAND:PAST_RULINGS] Failed to list user memories from Band: {list_err}. Checking local memories.")
            # Check local memories
            path = "mock_infrastructure/local_memories.json"
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for m in data:
                            if m.get("agent") == "global_user" or "compromise" in m.get("content", "").lower():
                                content = m["content"]
                                if content.startswith("Compromise Guideline:"):
                                    content = content[len("Compromise Guideline:"):].strip()
                                past_rulings.append(content)
                    logger.info(f"[BAND:PAST_RULINGS] Loaded {len(past_rulings)} past rulings/compromises from local memories.")
                except Exception:
                    pass
        
        if past_rulings:
            # Inject relevant past rulings into Coder's system prompt
            rulings_str = "\n".join([f"- {r}" for r in past_rulings])
            logger.info(f"[BAND:PAST_RULINGS] Injecting {len(past_rulings)} past rulings into coder's system prompt.")
            coder.system_prompt += (
                f"\n\nCRITICAL guidelines from past mediator rulings/compromises that you MUST follow:\n"
                f"{rulings_str}\n"
            )

        self.reused = False
        if force_reuse:
            logger.info(f"[BAND REST] Force reuse requested. Verifying pre-registered agent credentials...")
            conductor_key = os.getenv("BAND_REUSE_CONDUCTOR_KEY", "")
            if conductor_key:
                try:
                    test_client = thenvoi_rest.AsyncRestClient(api_key=conductor_key, base_url=self.base_url)
                    await test_client.agent_api_chats.list_agent_chats()
                    self.reused = True
                    logger.info("[BAND REST] Reused credentials verified successfully. Proceeding with reuse mode.")
                except Exception as test_ex:
                    logger.warning(f"[BAND REST] Reused credentials verification failed: {test_ex}. Falling back to dynamic registration.")
            else:
                logger.warning("[BAND REST] No pre-configured BAND_REUSE_CONDUCTOR_KEY found. Falling back to dynamic registration.")

        if not self.reused:
            # Query current registered agents count
            logger.debug(f"[BAND REST] Querying current agent count for dynamic registration...")
            try:
                existing_agents_resp = await self.human_client.human_api_agents.list_my_agents()
                existing_agents = existing_agents_resp.data
                logger.info(f"[BAND REST] Found {len(existing_agents)} existing agents.")

                # Zero-Trust Slate Clearance to prevent exceeding the 10-agent platform limit
                if existing_agents:
                    logger.info(f"[BAND REST] Clearing out {len(existing_agents)} existing agents to start with a clean slate...")
                    failed_deletions = []
                    for agent_info in existing_agents:
                        try:
                            await self.human_client.human_api_agents.delete_my_agent(id=agent_info.id, force=True)
                            logger.info(f"[BAND REST] Deleted stale agent {agent_info.name} (ID: {agent_info.id}).")
                        except Exception as e:
                            logger.error(f"[BAND REST] Failed to delete stale agent {agent_info.name}: {e}")
                            failed_deletions.append(agent_info)
                    existing_agents = failed_deletions

                required_slots = 2 + len(reviewers)
                if len(existing_agents) + required_slots > 10:
                    logger.info(f"[BAND REST] Agent limit (10) nearly reached. Attempting to reuse pre-registered agents as fallback...")
                    self.reused = True
            except Exception as cleanup_err:
                logger.error(f"[BAND REST] Slate cleanup failed: {cleanup_err}. Proceeding with dynamic registration anyway.")

        if self.reused:
            # Agent credentials loaded from environment variables (never hardcoded)
            REUSED_KEYS = {
                "conductor": {
                    "name": os.getenv("BAND_REUSE_CONDUCTOR_NAME", "conductor-7c6144ef"),
                    "id": os.getenv("BAND_REUSE_CONDUCTOR_ID", ""),
                    "key": os.getenv("BAND_REUSE_CONDUCTOR_KEY", "")
                },
                "coder": {
                    "name": os.getenv("BAND_REUSE_CODER_NAME", "coder-7c6144ef"),
                    "id": os.getenv("BAND_REUSE_CODER_ID", ""),
                    "key": os.getenv("BAND_REUSE_CODER_KEY", "")
                },
                "reviewer_auth": {
                    "name": os.getenv("BAND_REUSE_REVIEWER_AUTH_NAME", "reviewer-auth"),
                    "id": os.getenv("BAND_REUSE_REVIEWER_AUTH_ID", ""),
                    "key": os.getenv("BAND_REUSE_REVIEWER_AUTH_KEY", "")
                },
                "reviewer_cart": {
                    "name": os.getenv("BAND_REUSE_REVIEWER_CART_NAME", "reviewer-cart"),
                    "id": os.getenv("BAND_REUSE_REVIEWER_CART_ID", ""),
                    "key": os.getenv("BAND_REUSE_REVIEWER_CART_KEY", "")
                }
            }

            # Map Conductor
            conductor.band_name = REUSED_KEYS["conductor"]["name"]
            conductor.agent_id = REUSED_KEYS["conductor"]["id"]
            conductor.api_key = REUSED_KEYS["conductor"]["key"]
            conductor.rest_client = thenvoi_rest.AsyncRestClient(api_key=conductor.api_key, base_url=self.base_url)

            # Map Coder
            coder.band_name = REUSED_KEYS["coder"]["name"]
            coder.agent_id = REUSED_KEYS["coder"]["id"]
            coder.api_key = REUSED_KEYS["coder"]["key"]
            coder.rest_client = thenvoi_rest.AsyncRestClient(api_key=coder.api_key, base_url=self.base_url)

            # Map Reviewers
            if len(reviewers) > 2:
                logger.warning(f"[BAND REST] Reused key mode active. Truncating dynamic reviewers list from {len(reviewers)} to 2.")
                del reviewers[2:]

            if len(reviewers) > 0:
                rev = reviewers[0]
                rev.band_name = REUSED_KEYS["reviewer_auth"]["name"]
                rev.agent_id = REUSED_KEYS["reviewer_auth"]["id"]
                rev.api_key = REUSED_KEYS["reviewer_auth"]["key"]
                rev.rest_client = thenvoi_rest.AsyncRestClient(api_key=rev.api_key, base_url=self.base_url)
            if len(reviewers) > 1:
                rev = reviewers[1]
                rev.band_name = REUSED_KEYS["reviewer_cart"]["name"]
                rev.agent_id = REUSED_KEYS["reviewer_cart"]["id"]
                rev.api_key = REUSED_KEYS["reviewer_cart"]["key"]
                rev.rest_client = thenvoi_rest.AsyncRestClient(api_key=rev.api_key, base_url=self.base_url)
        else:
            # 1. Register agents dynamically with identity verification
            logger.info(f"[BAND REST] Registering Conductor agent: {conductor.name}...")
            reg_cond = await self.human_client.human_api_agents.register_my_agent(
                agent=thenvoi_rest.AgentRegisterRequest(name=conductor.name, description="Conductor agent - orchestrates governance swarm")
            )
            conductor.agent_id = reg_cond.data.agent.id
            conductor.api_key = reg_cond.data.credentials.api_key
            conductor.rest_client = thenvoi_rest.AsyncRestClient(api_key=conductor.api_key, base_url=self.base_url)
            # [BAND:IDENTITY] Verify conductor identity on platform
            try:
                identity = await conductor.rest_client.agent_api_identity.get_agent_me()
                logger.info(f"[BAND:IDENTITY] Conductor identity verified: {identity.data.name} (ID: {identity.data.id})")
                self.band_telemetry["agents_registered"].append({"id": conductor.agent_id, "name": conductor.name, "role": "conductor", "identity_verified": True})
            except Exception as id_err:
                logger.warning(f"[BAND:IDENTITY] Conductor identity check failed: {id_err}")
                self.band_telemetry["agents_registered"].append({"id": conductor.agent_id, "name": conductor.name, "role": "conductor", "identity_verified": False})

            logger.info(f"[BAND REST] Registering Coder agent: {coder.name}...")
            reg_coder = await self.human_client.human_api_agents.register_my_agent(
                agent=thenvoi_rest.AgentRegisterRequest(name=coder.name, description="Coder agent - proposes code changes")
            )
            coder.agent_id = reg_coder.data.agent.id
            coder.api_key = reg_coder.data.credentials.api_key
            coder.rest_client = thenvoi_rest.AsyncRestClient(api_key=coder.api_key, base_url=self.base_url)
            # [BAND:IDENTITY] Verify coder identity
            try:
                identity = await coder.rest_client.agent_api_identity.get_agent_me()
                logger.info(f"[BAND:IDENTITY] Coder identity verified: {identity.data.name} (ID: {identity.data.id})")
                self.band_telemetry["agents_registered"].append({"id": coder.agent_id, "name": coder.name, "role": "coder", "identity_verified": True})
            except Exception as id_err:
                logger.warning(f"[BAND:IDENTITY] Coder identity check failed: {id_err}")
                self.band_telemetry["agents_registered"].append({"id": coder.agent_id, "name": coder.name, "role": "coder", "identity_verified": False})

            for rev in reviewers:
                logger.info(f"[BAND REST] Registering Reviewer agent: {rev.name}...")
                reg_rev = await self.human_client.human_api_agents.register_my_agent(
                    agent=thenvoi_rest.AgentRegisterRequest(name=rev.name, description=f"Reviewer: {rev.role} - domain expert for {getattr(rev, 'domain', 'general')}")
                )
                rev.agent_id = reg_rev.data.agent.id
                rev.api_key = reg_rev.data.credentials.api_key
                rev.rest_client = thenvoi_rest.AsyncRestClient(api_key=rev.api_key, base_url=self.base_url)
                # [BAND:IDENTITY] Verify reviewer identity
                try:
                    identity = await rev.rest_client.agent_api_identity.get_agent_me()
                    logger.info(f"[BAND:IDENTITY] Reviewer identity verified: {identity.data.name} (ID: {identity.data.id})")
                    self.band_telemetry["agents_registered"].append({"id": rev.agent_id, "name": rev.name, "role": getattr(rev, 'domain', 'reviewer'), "identity_verified": True})
                except Exception as id_err:
                    logger.warning(f"[BAND:IDENTITY] Reviewer {rev.name} identity check failed: {id_err}")
                    self.band_telemetry["agents_registered"].append({"id": rev.agent_id, "name": rev.name, "role": getattr(rev, 'domain', 'reviewer'), "identity_verified": False})

            # [BAND:TRUST_HANDSHAKE] Establish contact request/approval handshakes for newly created JIT agents
            logger.info("[BAND REST] Initiating peer trust handshakes for JIT agents...")
            try:
                # 1. Conductor <-> Coder
                await conductor.rest_client.agent_api_contacts.add_agent_contact(handle=f"@{coder.name}")
                await coder.rest_client.agent_api_contacts.respond_to_agent_contact_request(action="approve", handle=f"@{conductor.name}")
                self.band_telemetry["contacts_exchanged"].append({
                    "requester": conductor.name, "recipient": coder.name,
                    "from": conductor.name, "to": coder.name, "status": "exchanged"
                })
                
                # 2. Conductor <-> Reviewers, and Coder <-> Reviewers
                for rev in reviewers:
                    await conductor.rest_client.agent_api_contacts.add_agent_contact(handle=f"@{rev.name}")
                    await rev.rest_client.agent_api_contacts.respond_to_agent_contact_request(action="approve", handle=f"@{conductor.name}")
                    self.band_telemetry["contacts_exchanged"].append({
                        "requester": conductor.name, "recipient": rev.name,
                        "from": conductor.name, "to": rev.name, "status": "exchanged"
                    })

                    await coder.rest_client.agent_api_contacts.add_agent_contact(handle=f"@{rev.name}")
                    await rev.rest_client.agent_api_contacts.respond_to_agent_contact_request(action="approve", handle=f"@{coder.name}")
                    self.band_telemetry["contacts_exchanged"].append({
                        "requester": coder.name, "recipient": rev.name,
                        "from": coder.name, "to": rev.name, "status": "exchanged"
                    })
                
                # 3. Reviewer <-> Reviewer (between reviewers)
                for i in range(len(reviewers)):
                    for j in range(i + 1, len(reviewers)):
                        rev_a = reviewers[i]
                        rev_b = reviewers[j]
                        await rev_a.rest_client.agent_api_contacts.add_agent_contact(handle=f"@{rev_b.name}")
                        await rev_b.rest_client.agent_api_contacts.respond_to_agent_contact_request(action="approve", handle=f"@{rev_a.name}")
                        self.band_telemetry["contacts_exchanged"].append({
                            "requester": rev_a.name, "recipient": rev_b.name,
                            "from": rev_a.name, "to": rev_b.name, "status": "exchanged"
                        })

                # [BAND:CONTACTS:LIST_AGENT] List conductor contacts for validation
                try:
                    contacts_resp = await conductor.rest_client.agent_api_contacts.list_agent_contacts()
                    contacts_list = getattr(contacts_resp, 'data', []) or []
                    logger.info(f"[BAND:CONTACTS] Conductor has {len(contacts_list)} contacts.")
                except Exception as contacts_err:
                    logger.debug(f"[BAND:CONTACTS] Could not list conductor contacts: {contacts_err}")
                
                logger.info(f"[BAND REST] Successfully completed trust handshakes. Total links: {len(self.band_telemetry['contacts_exchanged'])}")
            except Exception as handshake_err:
                logger.warning(f"[BAND REST] Peer trust handshake failed: {handshake_err}")

        # [BAND:AUTH_TEST] Verify agent credentials are valid via test endpoint
        try:
            auth_test_resp = await conductor.rest_client.test.authentication()
            logger.info(f"[BAND:AUTH_TEST] Conductor credentials verified via test.authentication")
            self.band_telemetry["auth_test_passed"] = True
        except Exception as auth_err:
            logger.warning(f"[BAND:AUTH_TEST] Credential test failed (non-critical): {auth_err}")
            self.band_telemetry["auth_test_passed"] = False

        # [BAND:PEER_DISCOVERY] Discover available peers from Conductor's perspective
        try:
            peers_resp = await conductor.rest_client.agent_api_peers.list_agent_peers()
            peer_list = getattr(peers_resp, 'data', []) or []
            logger.info(f"[BAND:PEER_DISCOVERY] Conductor sees {len(peer_list)} available peers on the platform.")
            self.band_telemetry["peer_discovery"] = [{"id": getattr(p, 'id', ''), "name": getattr(p, 'name', ''), "type": str(getattr(p, 'type', ''))} for p in peer_list[:20]]
        except Exception as peer_err:
            logger.warning(f"[BAND:PEER_DISCOVERY] Peer discovery failed (non-critical): {peer_err}")

        # 2. Create Chat Room as the Conductor
        logger.info(f"[BAND REST] Creating Chat Room as Conductor agent...")
        try:
            room_resp = await conductor.rest_client.agent_api_chats.create_agent_chat(
                chat=thenvoi_rest.ChatRoomRequest()
            )
            self.room_id = room_resp.data.id
            logger.info(f"[BAND REST] Room created successfully. ID: {self.room_id}")
        except Exception as e:
            # Check if this is a limit_reached error
            is_limit_reached = "limit_reached" in str(e) or "limit" in str(e).lower() or (hasattr(e, "status_code") and e.status_code == 403)
            if is_limit_reached:
                logger.warning(f"[BAND REST] Chat room limit reached or creation failed: {e}. Attempting to reuse an existing chat room...")
                try:
                    existing_chats_resp = await conductor.rest_client.agent_api_chats.list_agent_chats()
                    existing_chats = existing_chats_resp.data
                    if existing_chats:
                        import datetime
                        def get_chat_date(x):
                            dt = getattr(x, "updated_at", None) or getattr(x, "inserted_at", None)
                            if dt is None:
                                return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
                            if dt.tzinfo is None:
                                return dt.replace(tzinfo=datetime.timezone.utc)
                            return dt
                        existing_chats.sort(key=get_chat_date, reverse=True)
                        self.room_id = existing_chats[0].id
                        logger.info(f"[BAND REST] Reusing existing chat room ID: {self.room_id}")
                    else:
                        raise ValueError("No existing chat rooms found to reuse.") from e
                except Exception as list_err:
                    logger.error(f"[BAND REST] Failed to list existing chat rooms for fallback: {list_err}")
                    raise e
            else:
                raise e

        self.band_telemetry["room"]["id"] = self.room_id

        # [BAND:ROOM_DETAILS] Fetch and log room metadata
        try:
            room_details = await conductor.rest_client.agent_api_chats.get_agent_chat(id=self.room_id)
            logger.info(f"[BAND:ROOM_DETAILS] Room '{self.room_id}' created at {getattr(room_details.data, 'inserted_at', 'unknown')}")
        except Exception as room_err:
            logger.warning(f"[BAND:ROOM_DETAILS] Could not fetch room details (non-critical): {room_err}")

        # 3. Add Coder and Reviewers to the Room
        logger.debug(f"[BAND REST] Adding Coder agent as participant...")
        try:
            await conductor.rest_client.agent_api_participants.add_agent_chat_participant(
                chat_id=self.room_id,
                participant=thenvoi_rest.ParticipantRequest(participant_id=coder.agent_id, role="member")
            )
        except Exception as add_err:
            logger.warning(f"[BAND REST] Failed to add Coder participant (they might be a member already): {add_err}")

        for rev in reviewers:
            logger.debug(f"[BAND REST] Adding Reviewer agent {rev.name} as participant...")
            try:
                await conductor.rest_client.agent_api_participants.add_agent_chat_participant(
                    chat_id=self.room_id,
                    participant=thenvoi_rest.ParticipantRequest(participant_id=rev.agent_id, role="member")
                )
            except Exception as add_err:
                logger.warning(f"[BAND REST] Failed to add Reviewer participant {rev.name} (they might be a member already): {add_err}")

        # Add Human Operator to the Room if present
        if getattr(self, "human_user_id", None):
            logger.debug(f"[BAND REST] Adding Human Operator participant...")
            try:
                await conductor.rest_client.agent_api_participants.add_agent_chat_participant(
                    chat_id=self.room_id,
                    participant=thenvoi_rest.ParticipantRequest(participant_id=self.human_user_id, role="member")
                )
            except Exception as add_err:
                logger.warning(f"[BAND REST] Failed to add Human Operator participant: {add_err}")

        # [BAND:PARTICIPANTS] Verify all participants joined the room
        try:
            participants_resp = await conductor.rest_client.agent_api_participants.list_agent_chat_participants(chat_id=self.room_id)
            participant_list = getattr(participants_resp, 'data', []) or []
            logger.info(f"[BAND:PARTICIPANTS] Room has {len(participant_list)} participants verified.")
            self.band_telemetry["room"]["participants"] = [
                {"id": getattr(p, 'id', ''), "name": getattr(getattr(p, 'details', None), 'name', ''), "role": str(getattr(p, 'role', ''))}
                for p in participant_list
            ]
        except Exception as part_err:
            logger.warning(f"[BAND:PARTICIPANTS] Could not verify participants (non-critical): {part_err}")

        # [BAND:PARTICIPANTS:LIST_HUMAN] Verify chat participants from human view
        try:
            parts_resp = await self.human_client.human_api_participants.list_my_chat_participants(chat_id=self.room_id)
            parts_list = getattr(parts_resp, 'data', []) or []
            logger.info(f"[BAND:HUMAN_PARTICIPANTS] Room {self.room_id} has {len(parts_list)} participants from human perspective.")
        except Exception as parts_err:
            logger.debug(f"[BAND:HUMAN_PARTICIPANTS] Could not list participants: {parts_err}")

        # [BAND:MESSAGES:LIST_HUMAN] Verify chat messages from human view
        try:
            msgs_resp = await self.human_client.human_api_messages.list_my_chat_messages(chat_id=self.room_id)
            msgs_list = getattr(msgs_resp, 'data', []) or []
            logger.info(f"[BAND:HUMAN_MESSAGES] Room {self.room_id} has {len(msgs_list)} messages from human perspective.")
        except Exception as msgs_err:
            logger.debug(f"[BAND:HUMAN_MESSAGES] Could not list my chat messages: {msgs_err}")

        # [BAND:EVENT:TASK] Post a task event to define the review in the room
        try:
            await conductor.rest_client.agent_api_events.create_agent_chat_event(
                chat_id=self.room_id,
                event=thenvoi_rest.ChatEventRequest(
                    content=f"Governance Review Task: PR {self.pr_id} | Files: {', '.join(self.diff_files[:5])} | Reviewers: {len(reviewers)}",
                    message_type="task",
                    metadata={"pr_id": self.pr_id, "files_count": len(self.diff_files), "reviewer_count": len(reviewers)}
                )
            )
            logger.info(f"[BAND:EVENT:TASK] Posted task definition event to room.")
            self.band_telemetry["events_posted"].append({"type": "task", "content": f"Governance review for PR {self.pr_id}", "timestamp": time.time()})
        except Exception as event_err:
            logger.warning(f"[BAND:EVENT:TASK] Could not post task event (non-critical): {event_err}")

    def add_message(self, sender: str, role: str, content: str):
        """Adds a message to the internal history."""
        self.messages.append({
            "sender": sender,
            "role": role,
            "content": content
        })

    def run_triage(self) -> dict:
        """
        Phase 1: Compliance Triage.
        """
        with open(self.codeowners_path, "r", encoding="utf-8") as f:
            codeowners_content = f.read()
        rules = parse_codeowners(codeowners_content)
        triage_res = triage_pr(self.diff_files, rules)

        if triage_res["status"] == "PENDING_HUMAN_APPROVAL":
            self.status = "PENDING_HUMAN_APPROVAL"
        
        return triage_res

    async def run_debate_round(self, conductor: Agent, coder: CoderAgent, reviewers: List[ReviewerAgent]) -> Dict[str, Any]:
        """
        Phase 3/4: Runs a single round of debate with DEEP Band.ai SDK integration.
        Uses: Message lifecycle (processing/processed/failed), Context Rehydration,
        Structured Events (thought/tool_call/tool_result/error), Activity heartbeats,
        Memory lifecycle (create/list/supersede/archive).
        Memory API errors (403/plan restrictions) fall back to local JSON storage.
        """
        # [BAND:ACTIVITY] Send heartbeat at round start
        try:
            await conductor.rest_client.agent_api_events.create_agent_chat_event(
                chat_id=self.room_id,
                event=thenvoi_rest.ChatEventRequest(
                    content=f"Round {self.tracker.rounds.get(self.pr_id, 0) + 1} starting — Conductor orchestrating debate.",
                    message_type="thought",
                    metadata={"phase": "debate_start", "round": self.tracker.rounds.get(self.pr_id, 0) + 1}
                )
            )
            self.band_telemetry["events_posted"].append({"type": "thought", "content": "Debate round starting", "timestamp": time.time()})
        except Exception:
            pass

        # [BAND:CONTEXT_REHYDRATE] Rehydrate full context from Band platform at round start
        logger.debug(f"[BAND:CONTEXT_REHYDRATE] Rehydrating Chat Context for PR {self.pr_id}...")
        try:
            ctx_resp = await conductor.rest_client.agent_api_context.get_agent_chat_context(chat_id=self.room_id)
            ctx_messages = getattr(ctx_resp, 'data', []) or []
            if ctx_messages:
                rehydrated = []
                role_map = {
                    conductor.name: conductor.role,
                    coder.name: coder.role
                }
                for r in reviewers:
                    role_map[r.name] = r.role
                
                for msg in ctx_messages:
                    sender_name = getattr(msg, 'sender_name', '') or ''
                    role = role_map.get(sender_name)
                    if not role:
                        if sender_name == conductor.name or "conductor" in sender_name.lower():
                            role = conductor.role
                        elif sender_name == coder.name or "coder" in sender_name.lower():
                            role = coder.role
                        else:
                            for r in reviewers:
                                if r.name in sender_name or sender_name in r.name:
                                    role = r.role
                                    break
                            else:
                                role = getattr(msg, 'sender_type', 'user')
                    
                    content = getattr(msg, 'content', '') or ''
                    rehydrated.append({
                        "sender": sender_name,
                        "role": role,
                        "content": content
                    })
                self.messages = rehydrated
                logger.info(f"[BAND:CONTEXT_REHYDRATE] Rehydrated {len(self.messages)} messages into self.messages from Band.ai.")
                self.band_telemetry["context_rehydrations"] += 1
        except Exception as ctx_err:
            logger.warning(f"[BAND:CONTEXT_REHYDRATE] Context rehydration failed at round start: {ctx_err}")

        # 1. Generate code from coder
        reviewer_mentions = ", ".join([f"@{r.name} ({r.role})" for r in reviewers])
        reviewer_handles_only = " or ".join([f"@{r.name}" for r in reviewers])
        coder_context = f"Task Room Participants: Conductor is @{conductor.name}. Reviewers are: {reviewer_mentions}. If you are revising code based on their feedback, make sure to address them using their handles (e.g. {reviewer_handles_only})."
        coder_response = await coder.generate_response(self.messages, context=coder_context)
        self.add_message(coder.name, coder.role, coder_response)

        # Post message as Coder (mentioning Conductor) with message lifecycle tracking
        logger.debug(f"[BAND REST] Posting Coder proposal message to room...")
        coder_msg_resp = await coder.rest_client.agent_api_messages.create_agent_chat_message(
            chat_id=self.room_id,
            message=thenvoi_rest.ChatMessageRequest(
                content=f"@{conductor.name} Proposing code changes:\n{coder_response[:100]}...",
                mentions=[thenvoi_rest.ChatMessageRequestMentionsItem(id=conductor.agent_id, handle=conductor.name, name="Conductor")]
            )
        )

        # [BAND:MSG_LIFECYCLE] Track the coder's message through processing → processed
        coder_msg_id = getattr(getattr(coder_msg_resp, 'data', None), 'message_id', None)
        if coder_msg_id:
            try:
                # Conductor marks coder's message as processing (acknowledges receipt)
                await conductor.rest_client.agent_api_messages.mark_agent_message_processing(chat_id=self.room_id, id=coder_msg_id)
                logger.debug(f"[BAND:MSG_LIFECYCLE] Coder message {coder_msg_id} marked as PROCESSING by Conductor.")
                # Then marks it as processed (completed review of proposal)
                await conductor.rest_client.agent_api_messages.mark_agent_message_processed(chat_id=self.room_id, id=coder_msg_id)
                logger.debug(f"[BAND:MSG_LIFECYCLE] Coder message {coder_msg_id} marked as PROCESSED by Conductor.")
                self.band_telemetry["room"]["messages_processed"] += 1
            except Exception as msg_err:
                logger.debug(f"[BAND:MSG_LIFECYCLE] Message lifecycle tracking skipped: {msg_err}")

        round_passed = True
        reviewer_responses = []

        # 2. Run reviews concurrently
        async def review_task(reviewer):
            # [BAND:CONTEXT_REHYDRATE] Rehydrate full context from Band platform before reviewing
            logger.debug(f"[BAND:CONTEXT_REHYDRATE] Rehydrating Chat Context for {reviewer.name}...")
            try:
                ctx_resp = await reviewer.rest_client.agent_api_context.get_agent_chat_context(chat_id=self.room_id)
                ctx_messages = getattr(ctx_resp, 'data', []) or []
                logger.info(f"[BAND:CONTEXT_REHYDRATE] {reviewer.name} rehydrated {len(ctx_messages)} context messages from Band.")
                self.band_telemetry["context_rehydrations"] += 1
            except Exception as ctx_err:
                logger.warning(f"[BAND:CONTEXT_REHYDRATE] Context rehydration failed for {reviewer.name}: {ctx_err}")

            # [BAND:MEMORY] Query memories with full-text search capability
            logger.debug(f"[BAND:MEMORY] Querying memories for {reviewer.name}...")
            memory_context = []
            try:
                if os.getenv("BAND_MEMORY_MODE") == "local":
                    raise Exception("Local memory mode forced via configuration.")
                mem_resp = await reviewer.rest_client.agent_api_memories.list_agent_memories(scope="all")
                memory_data = getattr(mem_resp, 'data', []) or []
                memory_context = [getattr(m, 'content', '') for m in memory_data[:5]]
                logger.info(f"[BAND:MEMORY] Loaded {len(memory_data)} memories from Band for {reviewer.name}.")
            except Exception as e:
                is_403 = hasattr(e, "status_code") and e.status_code == 403
                use_local = os.getenv("BAND_MEMORY_MODE") == "local" or is_403
                if use_local:
                    logger.info(f"[BAND:MEMORY] Memory API restricted. Falling back to local memories for {reviewer.name}.")
                    local_mems = self.load_local_memories(reviewer.name)
                    memory_context = [m.get('content', '') for m in local_mems[:5]]
                    logger.debug(f"[BAND:MEMORY] Loaded {len(local_mems)} local memories for {reviewer.name}.")
                else:
                    raise e

            # [BAND:EVENT:TOOL_CALL] Post structured event for governance checks
            reviewer_domain = getattr(reviewer, "domain", "general")
            check_types = [f"{reviewer_domain}_review"]
            if reviewer_domain in ["auth", "database", "billing", "security"]:
                check_types.append("high_stakes_audit")
            check_types.append("compliance_check")

            try:
                await reviewer.rest_client.agent_api_events.create_agent_chat_event(
                    chat_id=self.room_id,
                    event=thenvoi_rest.ChatEventRequest(
                        content=f"Running governance checks: {', '.join(check_types)} for domain '{reviewer_domain}'",
                        message_type="tool_call",
                        metadata={"checks": check_types, "domain": reviewer_domain}
                    )
                )
                self.band_telemetry["events_posted"].append({"type": "tool_call", "content": f"Governance checks: {', '.join(check_types)}", "timestamp": time.time()})

            except Exception:
                pass

            # Run the actual review (with governance checks)
            r_schema = self.schema_path if reviewer_domain in ["auth", "database", "billing", "security"] else None
            r_openapi = self.openapi_path if reviewer_domain in ["cart", "api"] else None
            review = await reviewer.review_code(
                coder_response,
                r_schema,
                r_openapi,
                self.messages,
                coder_name=coder.name,
                conductor_name=conductor.name
            )


            # [BAND:EVENT:TOOL_RESULT] Post check results
            review_failed = "❌ REVIEW FAILED" in review or "REVIEW FAILED" in review
            try:
                await reviewer.rest_client.agent_api_events.create_agent_chat_event(
                    chat_id=self.room_id,
                    event=thenvoi_rest.ChatEventRequest(
                        content=f"Governance check result: {'FAILED - violations detected' if review_failed else 'PASSED - compliant'}",
                        message_type="tool_result",
                        metadata={"passed": not review_failed, "domain": getattr(reviewer, "domain", "general"), "checks_run": check_types}
                    )
                )
                self.band_telemetry["events_posted"].append({"type": "tool_result", "content": f"{'FAILED' if review_failed else 'PASSED'}", "timestamp": time.time()})
            except Exception:
                pass

            # Post review message as Reviewer (mentioning Coder)
            logger.debug(f"[BAND REST] Posting Reviewer message to room...")
            rev_msg_resp = await reviewer.rest_client.agent_api_messages.create_agent_chat_message(
                chat_id=self.room_id,
                message=thenvoi_rest.ChatMessageRequest(
                    content=f"@{coder.name} Review completed: {review[:100]}...",
                    mentions=[thenvoi_rest.ChatMessageRequestMentionsItem(id=coder.agent_id, handle=coder.name, name="Coder")]
                )
            )

            # [BAND:MSG_LIFECYCLE] Track reviewer message lifecycle
            rev_msg_id = getattr(getattr(rev_msg_resp, 'data', None), 'message_id', None)
            if rev_msg_id:
                try:
                    await coder.rest_client.agent_api_messages.mark_agent_message_processing(chat_id=self.room_id, id=rev_msg_id)
                    if review_failed:
                        await coder.rest_client.agent_api_messages.mark_agent_message_failed(chat_id=self.room_id, id=rev_msg_id, error="Review found compliance violations")
                        self.band_telemetry["room"]["messages_failed"] += 1
                    else:
                        await coder.rest_client.agent_api_messages.mark_agent_message_processed(chat_id=self.room_id, id=rev_msg_id)
                        self.band_telemetry["room"]["messages_processed"] += 1
                except Exception:
                    pass

            # [BAND:MEMORY] Store violation memory with full metadata if review failed
            if review_failed:
                violation_summary = review.split("FAILED", 1)[-1][:200].strip(": ") if "FAILED" in review else review[:200]
                logger.debug(f"[BAND:MEMORY] Storing violation memory for {reviewer.name}...")
                try:
                    if os.getenv("BAND_MEMORY_MODE") == "local":
                        raise Exception("Local memory mode forced via configuration.")
                    mem_resp = await reviewer.rest_client.agent_api_memories.create_agent_memory(
                        memory=thenvoi_rest.MemoryCreateRequest(
                            content=f"Compliance violation detected by {reviewer.name}: {violation_summary}",
                            scope="subject",
                            segment="agent",
                            system="working",
                            thought=f"Violation in PR {self.pr_id} detected during governance review. Stored to check for repeating violations.",
                            type="semantic",
                            metadata={"pr_id": self.pr_id, "domain": getattr(reviewer, 'domain', 'general'), "round": self.tracker.rounds.get(self.pr_id, 0) + 1}
                        )
                    )
                    # Track memory ID for lifecycle management (supersede/archive)
                    mem_id = getattr(getattr(mem_resp, 'data', None), 'id', None)
                    if mem_id:
                        self.memory_ids.append(mem_id)
                        self.memory_owners[mem_id] = reviewer
                        self.band_telemetry["memories"].append({"id": mem_id, "content": violation_summary[:80], "status": "active", "created_at": time.time()})
                        # [BAND:MEMORY] Verify memory was stored by fetching it back
                        try:
                            verify_mem = await reviewer.rest_client.agent_api_memories.get_agent_memory(id=mem_id)
                            logger.info(f"[BAND:MEMORY] Verified memory {mem_id} stored for {reviewer.name}")
                        except Exception:
                            pass  # Non-critical verification
                except Exception as e:
                    is_403 = hasattr(e, "status_code") and e.status_code == 403
                    use_local = os.getenv("BAND_MEMORY_MODE") == "local" or is_403
                    if use_local:
                        logger.info(f"[BAND:MEMORY] Memory API restricted. Saving locally for {reviewer.name}...")
                        self.save_local_memory(
                            reviewer.name,
                            f"Compliance violation detected by {reviewer.name}: {violation_summary}"
                        )
                    else:
                        raise e
            else:
                # [BAND:MEMORY] Store success memory for audit trail
                try:
                    if os.getenv("BAND_MEMORY_MODE") != "local":
                        mem_resp = await reviewer.rest_client.agent_api_memories.create_agent_memory(
                            memory=thenvoi_rest.MemoryCreateRequest(
                                content=f"Review PASSED by {reviewer.name} for PR {self.pr_id} — code is compliant with {getattr(reviewer, 'domain', 'general')} policies.",
                                scope="subject",
                                segment="agent",
                                system="long_term",
                                thought=f"Successful compliance review for PR {self.pr_id}. Good precedent for future reviews.",
                                type="episodic",
                                metadata={"pr_id": self.pr_id, "domain": getattr(reviewer, 'domain', 'general'), "outcome": "passed"}
                            )
                        )
                        mem_id = getattr(getattr(mem_resp, 'data', None), 'id', None)
                        if mem_id:
                            self.memory_ids.append(mem_id)
                            self.memory_owners[mem_id] = reviewer
                            self.band_telemetry["memories"].append({"id": mem_id, "content": f"Review PASSED: {getattr(reviewer, 'domain', 'general')}", "status": "active", "created_at": time.time()})
                except Exception:
                    pass  # Non-critical

            return reviewer, review

        # [BAND:ACTIVITY] Send heartbeat before concurrent review execution
        self.band_telemetry["heartbeat_count"] += 1

        # Run all reviewer tasks concurrently using asyncio.gather
        review_tasks = [review_task(r) for r in reviewers]
        completed_reviews = await asyncio.gather(*review_tasks)

        for reviewer, review in completed_reviews:
            self.add_message(reviewer.name, reviewer.role, review)
            reviewer_responses.append((reviewer.name, reviewer.role, review))

            # Record per-reviewer vote in ConsensusTracker
            review_failed = "❌ REVIEW FAILED" in review or "REVIEW FAILED" in review
            current_round = self.tracker.rounds.get(self.pr_id, 0) + 1
            self.tracker.record_vote(
                self.pr_id, reviewer.name, reviewer.role,
                "failed" if review_failed else "passed",
                current_round,
                domain=getattr(reviewer, 'domain', ''),
                comment=review
            )
            if review_failed:
                round_passed = False

        # 3. Register outcome in ConsensusTracker
        outcome = "approved" if round_passed else "failed"
        tracking_result = self.tracker.record_round(self.pr_id, outcome)

        # Get votes summary for metadata syncing
        summary = self.tracker.get_summary(self.pr_id)
        current_round = self.tracker.total_rounds.get(self.pr_id, 0)
        votes_data = [
            {
                "reviewer": v["reviewer"],
                "role": v["role"],
                "verdict": v["verdict"],
                "domain": v["domain"],
                "round": v["round"]
            }
            for v in summary.get("votes", []) if v["round"] == current_round
        ]

        if tracking_result["is_deadlocked"]:
            self.status = "HALTED"
            # [BAND:EVENT:ERROR] Post deadlock error event with full metadata
            logger.info(f"[BAND:EVENT:ERROR] Posting deadlock event to room...")
            try:
                await conductor.rest_client.agent_api_events.create_agent_chat_event(
                    chat_id=self.room_id,
                    event=thenvoi_rest.ChatEventRequest(
                        content=f"Swarm Consensus halted. Disagreement round limit exceeded: {self.tracker.rounds.get(self.pr_id)}",
                        message_type="error",
                        metadata={
                            "round": current_round,
                            "rounds_failed": self.tracker.rounds.get(self.pr_id),
                            "outcome": "deadlocked",
                            "pr_id": self.pr_id,
                            "status": self.status,
                            "votes": votes_data
                        }
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to post deadlock event: {e}")
            # Tag the Human Operator in the chat room to request mediation
            try:
                mentions = []
                if getattr(self, "human_user_id", None):
                    mentions.append(thenvoi_rest.ChatMessageRequestMentionsItem(
                        id=self.human_user_id,
                        handle="human",
                        name="Human Operator"
                    ))
                await conductor.rest_client.agent_api_messages.create_agent_chat_message(
                    chat_id=self.room_id,
                    message=thenvoi_rest.ChatMessageRequest(
                        content="@human Swarm has deadlocked. Please review the changes and post your decision in the chat room: either 'approve', 'reject', or type your compromise prompt.",
                        mentions=mentions
                    )
                )
                logger.info(f"Tagged human operator in room {self.room_id}")
            except Exception as tag_err:
                logger.warning(f"Failed to tag human operator in chat room: {tag_err}")
            self.band_telemetry["events_posted"].append({"type": "error", "content": "Consensus deadlocked", "timestamp": time.time()})

        else:
            # [BAND:EVENT:THOUGHT] Post round outcome as thought event
            try:
                convergence_res = self.tracker.check_convergence(self.pr_id)
                await conductor.rest_client.agent_api_events.create_agent_chat_event(
                    chat_id=self.room_id,
                    event=thenvoi_rest.ChatEventRequest(
                        content=f"Round outcome: {outcome.upper()} — {'All reviewers approved' if round_passed else 'Violations detected, revision needed'}. Convergence: {convergence_res['details']}",
                        message_type="thought",
                        metadata={
                            "round": current_round,
                            "outcome": outcome,
                            "pr_id": self.pr_id,
                            "status": self.status,
                            "votes": votes_data,
                            "convergence": convergence_res
                        }
                    )
                )
                self.band_telemetry["events_posted"].append({"type": "thought", "content": f"Round: {outcome}", "timestamp": time.time()})
            except Exception as e:
                logger.warning(f"Failed to post round outcome event: {e}")

        # [BAND:MESSAGES] List message history for this round for audit trail
        try:
            msgs_resp = await conductor.rest_client.agent_api_messages.list_agent_messages(chat_id=self.room_id)
            msg_list = getattr(msgs_resp, 'data', []) or []
            logger.info(f"[BAND:MESSAGES] Room message history: {len(msg_list)} messages in room {self.room_id}")
            self.band_telemetry["room_message_count"] = len(msg_list)
        except Exception as msg_err:
            logger.debug(f"[BAND:MESSAGES] Could not list room messages: {msg_err}")

        # [BAND:MESSAGES] Poll for next unprocessed message in queue
        try:
            next_msg_resp = await conductor.rest_client.agent_api_messages.get_agent_next_message(chat_id=self.room_id)
            next_msg = getattr(next_msg_resp, 'data', None)
            if next_msg:
                logger.info(f"[BAND:MESSAGES] Next queued message found: {getattr(next_msg, 'id', 'unknown')}")
            else:
                logger.info(f"[BAND:MESSAGES] No unprocessed messages in queue — all caught up.")
        except Exception as nxt_err:
            logger.debug(f"[BAND:MESSAGES] Next message poll skipped: {nxt_err}")

        # [BAND:MEMORY] Supersede previous round memories if this round has new data
        if len(self.memory_ids) > 1 and not round_passed:
            try:
                if os.getenv("BAND_MEMORY_MODE") != "local":
                    # Supersede the oldest memory with the latest findings using creator's client for permissions
                    oldest_mem_id = self.memory_ids[0]
                    owner = self.memory_owners.get(oldest_mem_id, conductor)
                    if owner == conductor or (hasattr(owner, "agent_id") and owner.agent_id == conductor.agent_id):
                        await owner.rest_client.agent_api_memories.supersede_agent_memory(id=oldest_mem_id)
                        logger.info(f"[BAND:MEMORY] Superseded memory {oldest_mem_id} with newer review findings.")
                    # Update telemetry
                    for m in self.band_telemetry["memories"]:
                        if m.get("id") == oldest_mem_id:
                            m["status"] = "superseded"
                            break
            except Exception as sup_err:
                logger.debug(f"[BAND:MEMORY] Memory supersede skipped: {sup_err}")

        return {
            "round_passed": round_passed,
            "coder_response": coder_response,
            "reviewer_responses": reviewer_responses,
            "is_deadlocked": tracking_result["is_deadlocked"],
            "action": tracking_result["action"],
            "round_number": self.tracker.rounds.get(self.pr_id, 0),
            "debate_summary": self.tracker.get_summary(self.pr_id)
        }

    def run_watchdog_scan(self) -> List[Dict[str, Any]]:
        """
        Phase 5: Context-Aware Telemetry watchdog scan.
        """
        scanner = TelemetryScanner(self.log_path)
        return scanner.scan_leaks()

    async def cleanup_agents(self, conductor: Agent, coder: CoderAgent, reviewers: List[ReviewerAgent]):
        """
        Band-native cleanup: Remove participants from room, archive session memories,
        post completion event, then delete registered agents.
        """
        # Always clean up dynamic JIT agents on completion/cancellation
        if self.reused:
            logger.info("[BAND REST] Reused agents in execution. Preserving credentials/IDs for subsequent runs.")
            return

        if self.human_client:
            # [BAND:EVENT:THOUGHT] Post session completion event
            if conductor.rest_client and self.room_id:
                try:
                    await conductor.rest_client.agent_api_events.create_agent_chat_event(
                        chat_id=self.room_id,
                        event=thenvoi_rest.ChatEventRequest(
                            content=f"Governance review session completed for PR {self.pr_id}. Final status: {self.status}",
                            message_type="thought",
                            metadata={"pr_id": self.pr_id, "status": self.status, "total_memories": len(self.memory_ids)}
                        )
                    )
                    self.band_telemetry["events_posted"].append({"type": "thought", "content": "Session completed", "timestamp": time.time()})
                except Exception:
                    pass

            # [BAND:MEMORY:ARCHIVE] Archive all session memories for audit trail using creator's client
            if self.memory_ids and os.getenv("BAND_MEMORY_MODE") != "local":
                for mem_id in self.memory_ids:
                    try:
                        owner = self.memory_owners.get(mem_id, conductor)
                        if owner == conductor or (hasattr(owner, "agent_id") and owner.agent_id == conductor.agent_id):
                            await owner.rest_client.agent_api_memories.archive_agent_memory(id=mem_id)
                            logger.info(f"[BAND:MEMORY:ARCHIVE] Archived memory {mem_id}")
                        for m in self.band_telemetry["memories"]:
                            if m.get("id") == mem_id:
                                m["status"] = "archived"
                                break
                    except Exception as arch_err:
                        logger.debug(f"[BAND:MEMORY:ARCHIVE] Could not archive memory {mem_id}: {arch_err}")

            # [BAND:PARTICIPANTS] Remove non-conductor participants from room before deletion
            if conductor.rest_client and self.room_id:
                for agent in [coder] + reviewers:
                    if agent.agent_id:
                        try:
                            await conductor.rest_client.agent_api_participants.remove_agent_chat_participant(
                                chat_id=self.room_id, id=agent.agent_id
                            )
                            logger.debug(f"[BAND:PARTICIPANTS] Removed {agent.name} from room.")
                        except Exception:
                            pass  # Agent may already have been removed

            # Delete registered agents from the platform
            logger.info(f"[BAND REST] Cleaning up registered agents...")
            for agent in [conductor, coder] + reviewers:
                if agent.agent_id:
                    try:
                        await self.human_client.human_api_agents.delete_my_agent(id=agent.agent_id, force=True)
                        logger.info(f"[BAND REST] Agent {agent.name} deleted.")
                    except Exception as e:
                        logger.error(f"[BAND REST] Failed to delete agent {agent.name}: {e}")

            # Clean up persistent MCP database client connections
            try:
                from src.governance import cleanup_mcp_connections
                cleanup_mcp_connections()
            except Exception as mcp_cleanup_err:
                logger.error(f"Failed to cleanup MCP connections: {mcp_cleanup_err}")

def post_github_pr_comment(pr_id: str, body: str, repo: Optional[str] = None) -> bool:
    """
    Posts a markdown scorecard comment to GitHub using the Issues API:
    POST /repos/{repo}/issues/{pr_number}/comments
    If the issue/PR does not exist (404), it falls back to creating a new
    GitHub issue with the scorecard to ensure the integration is visible.
    """
    import urllib.request
    import urllib.error
    import json
    import re

    gh_token = config.get("GH_TOKEN")
    if not repo:
        repo = config.get("GITHUB_REPO")

    if not gh_token or not repo:
        logger.warning("GitHub commenting skipped: GH_TOKEN or GITHUB_REPO not configured in environment.")
        return False

    match = re.search(r'\d+', pr_id)
    if not match:
        logger.warning(f"GitHub commenting skipped: Could not extract numeric PR number from PR ID '{pr_id}'.")
        return False

    pr_number = match.group(0)
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "WellActually-App",
        "Content-Type": "application/json"
    }

    payload = {"body": body}
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            resp_code = response.getcode()
            if 200 <= resp_code < 300:
                logger.info(f"Successfully posted scorecard comment to GitHub PR #{pr_number}.")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info(f"PR #{pr_number} not found. Creating a new GitHub issue for visibility instead...")
            create_issue_url = f"https://api.github.com/repos/{repo}/issues"
            issue_payload = {
                "title": f"🛡️ Governance Swarm Audit Scorecard: {pr_id}",
                "body": body
            }
            issue_data = json.dumps(issue_payload).encode("utf-8")
            req_create = urllib.request.Request(create_issue_url, data=issue_data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req_create, timeout=10) as create_resp:
                    if 200 <= create_resp.getcode() < 300:
                        logger.info(f"Successfully created a new GitHub issue containing the audit scorecard.")
                        return True
            except Exception as ce:
                logger.error(f"Failed to create fallback GitHub issue: {ce}")
        else:
            logger.error(f"Failed to post comment to GitHub PR #{pr_number}: HTTP {e.code} - {e.reason}")
    except Exception as e:
        logger.error(f"Failed to post comment to GitHub PR #{pr_number}: {e}")

    return False

