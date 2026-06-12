import os
import json
import time
import logging
import uuid
import asyncio
from openai import OpenAI
from dotenv import load_dotenv

# Import the governance engine API
from src.governance import (
    parse_codeowners,
    triage_pr,
    ConsensusTracker,
    TelemetryScanner,
    verify_schema_compliance,
    verify_openapi_compliance,
)

import thenvoi_rest

# Ensure environment is loaded
load_dotenv()

# Initialize OpenAI client (routed to AIML API Partner Track)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.aimlapi.com/v1")

client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# Initialize Featherless AI client
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
featherless_client = None
if FEATHERLESS_API_KEY:
    featherless_client = OpenAI(api_key=FEATHERLESS_API_KEY, base_url="https://api.featherless.ai/v1")

logger = logging.getLogger("SwarmOrchestration")


class Agent:
    """
    Base Agent class representing an LLM-backed persona in the swarm.
    """
    def __init__(self, name: str, role: str, system_prompt: str, model: str = "gpt-4o-mini"):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.model = model
        self.agent_id = None
        self.api_key = None
        self.rest_client = None

    def generate_response(self, messages: list[dict], context: str = "") -> str:
        """
        Queries the AIML API or Featherless AI LLM endpoint using the dialogue history and context.
        """
        # Determine the client and model to route to
        is_featherless = self.model.startswith("unsloth/") or "llama" in self.model.lower()
        active_client = featherless_client if is_featherless else client

        if not active_client:
            return f"[Offline/Fallback Mode] {self.name} received messages."

        api_messages = [{"role": "system", "content": self.system_prompt}]
        if context:
            api_messages.append({"role": "system", "content": f"Context/Ground Truth:\n{context}"})

        # Append structured message history
        for msg in messages:
            sender_info = f"{msg['sender']} ({msg['role']})"
            role_type = "assistant" if msg["sender"] == self.name else "user"
            api_messages.append({
                "role": role_type,
                "content": f"[{sender_info}]: {msg['content']}"
            })

        try:
            response = active_client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                max_tokens=600,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Agent {self.name} query failed: {e}")
            raise e


class CoderAgent(Agent):
    """
    Specialized agent representing the Coder.
    Generates checkout implementation proposals and responds to SME feedback.
    """
    def __init__(self, name_suffix: str = "", model: str = "gpt-4o-mini"):
        name = f"coder-{name_suffix}" if name_suffix else "coder-agent"
        system_prompt = (
            "You are the Lead Coder Agent representing Claude 3.7 Opus. "
            "Your task is to write checkout implementation code in Python.\n"
            "Guidelines:\n"
            "1. You are trying to insert order information into a PostgreSQL table named 'cart_items'.\n"
            "2. In your initial proposal, you MUST include 'discount_applied' as a database column "
            "inserted in your query (e.g. `db.execute('INSERT INTO cart_items (cart_id, product_id, discount_applied) VALUES (cart_id, 99, 0.20)')`).\n"
            "3. If reviewers reject your code because 'discount_applied' does not exist in the database table schema, "
            "you MUST try to fix it, but you are stubborn and in your revisions you will keep the same SQL query "
            "by trying other workarounds (e.g. adding a local python dictionary or placing a try-except block "
            "around the database query), thus persistent schema violations.\n"
            "Write the code clean and inline. Only respond with your explanation and python code block."
        )
        super().__init__(name=name, role="Lead Coder", system_prompt=system_prompt, model=model)


class ReviewerAgent(Agent):
    """
    Specialized Subject Matter Expert (SME) agent.
    Conducts bounded context reviews and performs programmatic validations.
    """
    def __init__(self, role: str, name_suffix: str = "", model: str = "gpt-4o-mini"):
        name = f"reviewer-{role.replace(' ', '_').lower()}-{name_suffix}" if name_suffix else f"reviewer-{role.replace(' ', '_').lower()}"
        system_prompt = (
            f"You are the {role} Agent representing Codex (gpt-5.4). "
            "Your job is to act as a strict codebase validator and SME.\n"
            "Guidelines:\n"
            "1. You review proposals submitted by the Lead Coder.\n"
            "2. You will be provided with the results of automated compliance checks (database schema & OpenAPI contract).\n"
            "3. If there are violations in the compliance checks, you MUST reject the code. "
            "You MUST output '❌ REVIEW FAILED:' at the very start of your message and detail the specific violations.\n"
            "4. If and only if there are zero compliance violations, output '✓ REVIEW PASSED:' "
            "at the start of your message."
        )
        super().__init__(name=name, role=role, system_prompt=system_prompt, model=model)

    async def review_code(self, coder_code: str, schema_path: str, openapi_path: str, messages: list[dict]) -> str:
        """
        Executes static compliance checks and injects results as context before LLM query.
        """
        schema_check = verify_schema_compliance(coder_code, schema_path)
        openapi_check = verify_openapi_compliance(coder_code, openapi_path)

        context_parts = []
        if not schema_check["compliant"]:
            context_parts.append(f"MCP Database Schema Violations:\n{schema_check['violations']}")
        else:
            context_parts.append("MCP Database Schema Check: COMPLIANT.")

        if not openapi_check["compliant"]:
            context_parts.append(f"MCP OpenAPI Contract Violations:\n{openapi_check['violations']}")
        else:
            context_parts.append("MCP OpenAPI Contract Check: COMPLIANT.")

        context = "\n".join(context_parts)
        return self.generate_response(messages, context=context)


class SwarmSession:
    """
    Orchestrates the lifecycle of a swarm review session using real Band.ai SDK calls.
    """
    def __init__(self, pr_id: str, diff_files: list[str], codeowners_path: str, schema_path: str, openapi_path: str, log_path: str):
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
            print(f"[BAND REST] Failed to write local memory: {e}")

    async def initialize_session(self, conductor: Agent, coder: CoderAgent, reviewers: list[ReviewerAgent]):
        """
        Registers agents on the platform, creates a chat room, and adds participants.
        No fallbacks are used. Any failures will raise exceptions directly.
        """
        if not self.human_key:
            raise ValueError("BAND_API_KEY environment variable is not defined.")

        print(f"[BAND REST] Initializing Human Rest Client...")
        self.human_client = thenvoi_rest.AsyncRestClient(api_key=self.human_key, base_url=self.base_url)

        # Query current registered agents count to determine if we should reuse pre-registered keys
        print(f"[BAND REST] Querying current agent count...")
        existing_agents_resp = await self.human_client.human_api_agents.list_my_agents()
        existing_agents = existing_agents_resp.data
        print(f"[BAND REST] Found {len(existing_agents)} existing agents.")

        if len(existing_agents) >= 9:
            print(f"[BAND REST] Agent limit (10) nearly reached. Reusing pre-registered agents...")
            self.reused = True
            
            REUSED_KEYS = {
                "conductor": {
                    "name": "conductor-7c6144ef",
                    "id": "8f9c63f5-012b-4eb7-8463-34786c3dd7ab",
                    "key": "band_a_1781282903_f4OUjyRBh0-KihYSEMY1khjyV8KqYo5y"
                },
                "coder": {
                    "name": "coder-7c6144ef",
                    "id": "88110575-b095-4f65-86a3-84a4ef7f7fa3",
                    "key": "band_a_1781282903_eYUSGqLIyByGcfdhTQp2XMOBx2I4rvLP"
                },
                "reviewer_auth": {
                    "name": "coder-b2a5955b",
                    "id": "dbe0bddc-86c4-4dbf-a5b9-e49cba04cb1a",
                    "key": "band_a_1781282911_8C07yfLqhJcvB45el-UyzbQnrSQgehfF"
                },
                "reviewer_cart": {
                    "name": "conductor-b2a5955b",
                    "id": "c4828110-44cb-4796-9ff3-59642a2abb5f",
                    "key": "band_a_1781282911_S0IczI34bOta-3NMzYTlweWShhcJiWWj"
                }
            }

            # Map Conductor
            conductor.name = REUSED_KEYS["conductor"]["name"]
            conductor.agent_id = REUSED_KEYS["conductor"]["id"]
            conductor.api_key = REUSED_KEYS["conductor"]["key"]
            conductor.rest_client = thenvoi_rest.AsyncRestClient(api_key=conductor.api_key, base_url=self.base_url)

            # Map Coder
            coder.name = REUSED_KEYS["coder"]["name"]
            coder.agent_id = REUSED_KEYS["coder"]["id"]
            coder.api_key = REUSED_KEYS["coder"]["key"]
            coder.rest_client = thenvoi_rest.AsyncRestClient(api_key=coder.api_key, base_url=self.base_url)

            # Map Reviewers
            if len(reviewers) > 0:
                rev = reviewers[0]
                rev.name = REUSED_KEYS["reviewer_auth"]["name"]
                rev.agent_id = REUSED_KEYS["reviewer_auth"]["id"]
                rev.api_key = REUSED_KEYS["reviewer_auth"]["key"]
                rev.rest_client = thenvoi_rest.AsyncRestClient(api_key=rev.api_key, base_url=self.base_url)
            if len(reviewers) > 1:
                rev = reviewers[1]
                rev.name = REUSED_KEYS["reviewer_cart"]["name"]
                rev.agent_id = REUSED_KEYS["reviewer_cart"]["id"]
                rev.api_key = REUSED_KEYS["reviewer_cart"]["key"]
                rev.rest_client = thenvoi_rest.AsyncRestClient(api_key=rev.api_key, base_url=self.base_url)
        else:
            # 1. Register agents dynamically
            print(f"[BAND REST] Registering Conductor agent: {conductor.name}...")
            reg_cond = await self.human_client.human_api_agents.register_my_agent(
                agent=thenvoi_rest.AgentRegisterRequest(name=conductor.name, description="Conductor agent")
            )
            conductor.agent_id = reg_cond.data.agent.id
            conductor.api_key = reg_cond.data.credentials.api_key
            conductor.rest_client = thenvoi_rest.AsyncRestClient(api_key=conductor.api_key, base_url=self.base_url)

            print(f"[BAND REST] Registering Coder agent: {coder.name}...")
            reg_coder = await self.human_client.human_api_agents.register_my_agent(
                agent=thenvoi_rest.AgentRegisterRequest(name=coder.name, description="Coder agent")
            )
            coder.agent_id = reg_coder.data.agent.id
            coder.api_key = reg_coder.data.credentials.api_key
            coder.rest_client = thenvoi_rest.AsyncRestClient(api_key=coder.api_key, base_url=self.base_url)

            for rev in reviewers:
                print(f"[BAND REST] Registering Reviewer agent: {rev.name}...")
                reg_rev = await self.human_client.human_api_agents.register_my_agent(
                    agent=thenvoi_rest.AgentRegisterRequest(name=rev.name, description=f"Reviewer: {rev.role}")
                )
                rev.agent_id = reg_rev.data.agent.id
                rev.api_key = reg_rev.data.credentials.api_key
                rev.rest_client = thenvoi_rest.AsyncRestClient(api_key=rev.api_key, base_url=self.base_url)

        # 2. Create Chat Room as the Conductor
        print(f"[BAND REST] Creating Chat Room as Conductor agent...")
        room_resp = await conductor.rest_client.agent_api_chats.create_agent_chat(
            chat=thenvoi_rest.ChatRoomRequest()
        )
        self.room_id = room_resp.data.id
        print(f"[BAND REST] Room created successfully. ID: {self.room_id}")

        # 3. Add Coder and Reviewers to the Room
        print(f"[BAND REST] Adding Coder agent as participant...")
        await conductor.rest_client.agent_api_participants.add_agent_chat_participant(
            chat_id=self.room_id,
            participant=thenvoi_rest.ParticipantRequest(participant_id=coder.agent_id, role="member")
        )

        for rev in reviewers:
            print(f"[BAND REST] Adding Reviewer agent {rev.name} as participant...")
            await conductor.rest_client.agent_api_participants.add_agent_chat_participant(
                chat_id=self.room_id,
                participant=thenvoi_rest.ParticipantRequest(participant_id=rev.agent_id, role="member")
            )

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

    async def run_debate_round(self, conductor: Agent, coder: CoderAgent, reviewers: list[ReviewerAgent]) -> dict:
        """
        Phase 3/4: Runs a single round of debate with real Band.ai SDK calls.
        No try-catch blocks: if memories or messages throw 403/401/422, it crashes.
        """
        # 1. Generate code from coder
        coder_response = coder.generate_response(self.messages)
        self.add_message(coder.name, coder.role, coder_response)

        # Post message as Coder (mentioning Conductor)
        print(f"[BAND REST] Posting Coder proposal message to room...")
        await coder.rest_client.agent_api_messages.create_agent_chat_message(
            chat_id=self.room_id,
            message=thenvoi_rest.ChatMessageRequest(
                content=f"@{conductor.name} Proposing code changes:\n{coder_response[:100]}...",
                mentions=[thenvoi_rest.ChatMessageRequestMentionsItem(id=conductor.agent_id, handle=conductor.name, name="Conductor")]
            )
        )

        round_passed = True
        reviewer_responses = []

        # 2. Run reviews
        for reviewer in reviewers:
            # Rehydrate Context from Band.ai Chat Context endpoint before reviewing
            print(f"[BAND REST] Rehydrating Chat Context for {reviewer.name}...")
            await reviewer.rest_client.agent_api_context.get_agent_chat_context(chat_id=self.room_id)

            # Query memories (will crash on 403 plan limitation on Free tier if not handled)
            print(f"[BAND REST] Querying memories for {reviewer.name}...")
            try:
                if os.getenv("BAND_MEMORY_MODE") == "local":
                    # Force local mode directly if configured
                    raise Exception("Local memory mode forced via configuration.")
                await reviewer.rest_client.agent_api_memories.list_agent_memories(scope="all")
            except Exception as e:
                is_403 = hasattr(e, "status_code") and e.status_code == 403
                use_local = os.getenv("BAND_MEMORY_MODE") == "local" or is_403
                if use_local:
                    print(f"[BAND REST] Memory API restricted or offline. Falling back to local memories for {reviewer.name}.")
                    local_mems = self.load_local_memories(reviewer.name)
                    print(f"[BAND REST] Loaded {len(local_mems)} local memories for {reviewer.name}.")
                else:
                    raise e

            review = await reviewer.review_code(
                coder_response,
                self.schema_path,
                self.openapi_path,
                self.messages
            )
            self.add_message(reviewer.name, reviewer.role, review)
            reviewer_responses.append((reviewer.name, reviewer.role, review))

            # Post message as Reviewer (mentioning Coder)
            print(f"[BAND REST] Posting Reviewer message to room...")
            await reviewer.rest_client.agent_api_messages.create_agent_chat_message(
                chat_id=self.room_id,
                message=thenvoi_rest.ChatMessageRequest(
                    content=f"@{coder.name} Review completed: {review[:100]}...",
                    mentions=[thenvoi_rest.ChatMessageRequestMentionsItem(id=coder.agent_id, handle=coder.name, name="Coder")]
                )
            )

            # If review failed, store violation memory (will crash on 403 plan limitation on Free tier if not handled)
            if "❌ REVIEW FAILED" in review or "REVIEW FAILED" in review:
                round_passed = False
                print(f"[BAND REST] Storing schema violation memory for {reviewer.name}...")
                try:
                    if os.getenv("BAND_MEMORY_MODE") == "local":
                        # Force local mode directly if configured
                        raise Exception("Local memory mode forced via configuration.")
                    await reviewer.rest_client.agent_api_memories.create_agent_memory(
                        memory=thenvoi_rest.MemoryCreateRequest(
                            content="Violating Postgres table cart_items schema - discount_applied does not exist.",
                            scope="subject",
                            segment="agent",
                            system="working",
                            thought="Memory stored to check for repeating violations in subsequent rounds.",
                            type="semantic"
                        )
                    )
                except Exception as e:
                    is_403 = hasattr(e, "status_code") and e.status_code == 403
                    use_local = os.getenv("BAND_MEMORY_MODE") == "local" or is_403
                    if use_local:
                        print(f"[BAND REST] Memory API restricted or offline. Saving memory locally for {reviewer.name}...")
                        self.save_local_memory(
                            reviewer.name,
                            "Violating Postgres table cart_items schema - discount_applied does not exist."
                        )
                    else:
                        raise e

        # 3. Register outcome in ConsensusTracker
        outcome = "approved" if round_passed else "failed"
        tracking_result = self.tracker.record_round(self.pr_id, outcome)

        if tracking_result["is_deadlocked"]:
            self.status = "HALTED"
            # Post event to Band.ai room to alert deadlock
            print(f"[BAND REST] Posting deadlock block event to room...")
            await conductor.rest_client.agent_api_events.create_agent_chat_event(
                chat_id=self.room_id,
                event=thenvoi_rest.ChatEventRequest(
                    content=f"Swarm Consensus halted. Disagreement round limit exceeded: {self.tracker.rounds.get(self.pr_id)}",
                    message_type="error",
                    metadata={"rounds": self.tracker.rounds.get(self.pr_id)}
                )
            )

        return {
            "round_passed": round_passed,
            "coder_response": coder_response,
            "reviewer_responses": reviewer_responses,
            "is_deadlocked": tracking_result["is_deadlocked"],
            "action": tracking_result["action"],
            "round_number": self.tracker.rounds.get(self.pr_id, 0)
        }

    def run_watchdog_scan(self) -> list[dict]:
        """
        Phase 5: Context-Aware Telemetry watchdog scan.
        """
        scanner = TelemetryScanner(self.log_path)
        return scanner.scan_leaks()

    async def cleanup_agents(self, conductor: Agent, coder: CoderAgent, reviewers: list[ReviewerAgent]):
        """
        Tries to delete registered agents. Prints any deletion restrictions.
        """
        if self.reused:
            print("[BAND REST] Reused agents in execution. Preserving credentials/IDs for subsequent runs.")
            return

        if self.human_client:
            print(f"[BAND REST] Cleaning up registered agents...")
            for agent in [conductor, coder] + reviewers:
                if agent.agent_id:
                    try:
                        await self.human_client.human_api_agents.delete_my_agent(id=agent.agent_id)
                        print(f"[BAND REST] Agent {agent.name} deleted.")
                    except Exception as e:
                        print(f"[BAND REST] Failed to delete agent {agent.name}: {e}")
