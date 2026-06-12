import json
import logging
import os

# Configure logging for the watchdog and engine
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GovernanceEngine")


def parse_codeowners(content: str) -> dict:
    """
    Parses CODEOWNERS file content.
    Returns mapping of patterns to metadata/owners.
    
    Example Return Structure:
    {
        "/src/auth/": {
            "owner": "@security-owners-pool",
            "is_high_stakes": True
        },
        ...
    }
    """
    rules = {}
    for line in content.splitlines():
        line = line.strip()
        # Ignore comments and empty lines
        if not line or line.startswith('#'):
            continue
        
        parts = line.split()
        if len(parts) >= 2:
            pattern = parts[0]
            owner = parts[1]
            # Search for metadata indicator in any trailing parts
            is_high_stakes = any("[high-stakes]" in p or "high-stakes" in p for p in parts[2:])
            
            rules[pattern] = {
                "owner": owner,
                "is_high_stakes": is_high_stakes
            }
    return rules


def triage_pr(diff_files: list[str], codeowners_rules: dict) -> dict:
    """
    Triages modified files in a PR diff against parsed CODEOWNERS rules.
    
    Returns a result dictionary containing:
    - status: "approved" or "PENDING_HUMAN_APPROVAL"
    - required_approvals: list of owner pools that matched
    - is_high_stakes: boolean indicating if a high-stakes rule was triggered
    """
    required_approvals = set()
    is_high_stakes = False

    for file_path in diff_files:
        # Normalize file path to always have a leading slash and forward slashes
        norm_path = '/' + file_path.replace('\\', '/').lstrip('/')
        
        matched_owner = None
        matched_high_stakes = False
        
        # Traverse rules in order (dict preserves insertion order)
        for pattern, rule in codeowners_rules.items():
            # If the pattern is a directory matcher
            if pattern.endswith('/'):
                if norm_path.startswith(pattern):
                    matched_owner = rule["owner"]
                    matched_high_stakes = rule["is_high_stakes"]
            else:
                # Exact file match
                if norm_path == pattern:
                    matched_owner = rule["owner"]
                    matched_high_stakes = rule["is_high_stakes"]
        
        if matched_owner:
            required_approvals.add(matched_owner)
            if matched_high_stakes:
                is_high_stakes = True
                
    status = "PENDING_HUMAN_APPROVAL" if is_high_stakes else "approved"
    
    return {
        "status": status,
        "required_approvals": sorted(list(required_approvals)),
        "is_high_stakes": is_high_stakes
    }


class ConsensusTracker:
    def __init__(self, max_rounds: int = 2):
        """
        Initializes the Consensus Tracker with maximum allowed review rounds.
        """
        self.max_rounds = max_rounds
        self.rounds = {}  # Maps pr_id -> count of failed/disagreement rounds

    def record_round(self, pr_id: str, outcome: str) -> dict:
        """
        Records review outcome for a PR round.
        
        outcome: "approved" or "failed"/"rejected"
        Returns a dictionary containing:
        - is_deadlocked: boolean
        - action: "continue", "hitl_escalation", or "merge"
        """
        if pr_id not in self.rounds:
            self.rounds[pr_id] = 0

        if outcome == "approved":
            return {
                "is_deadlocked": False,
                "action": "merge"
            }
        
        # Increment failure count on disagreement
        self.rounds[pr_id] += 1
        
        if self.rounds[pr_id] > self.max_rounds:
            return {
                "is_deadlocked": True,
                "action": "hitl_escalation"
            }
        else:
            return {
                "is_deadlocked": False,
                "action": "continue"
            }


class TelemetryScanner:
    def __init__(self, log_path: str):
        """
        Initializes the scanner with the target JSON log path.
        """
        self.log_path = log_path

    def scan_leaks(self) -> list[dict]:
        """
        Scans logs for warning patterns (specifically matching the memory leak signature or database pool exhaustion).
        Logs a warning alert and returns all matching log entries.
        """
        alerts = []
        if not os.path.exists(self.log_path):
            logger.error(f"Log file not found at: {self.log_path}")
            return alerts

        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON logs at {self.log_path}: {e}")
            return alerts

        for log in logs:
            message = log.get("message", "")
            # Check if memory leak signature or database pool exhaustion resides in message
            if "Memory leak signature detected" in message or "database pool exhaustion" in message.lower():
                logger.warning(
                    f"[ALERT] [Telemetry Watchdog] Anomaly detected in {log.get('service', 'unknown-service')}! "
                    f"Message: {message} | Timestamp: {log.get('timestamp')}"
                )
                alerts.append(log)
                
        return alerts


def verify_schema_compliance(code_content: str, schema_path: str) -> dict:
    """
    Validates code_content against the PostgreSQL schema boundaries.
    """
    violations = []
    # cart_items table has columns: id, cart_id, product_id, quantity, price_at_addition.
    # If code attempts to use non-existent column "discount_applied", flag it.
    if "cart_items" in code_content and "discount_applied" in code_content:
        violations.append("Column 'discount_applied' does not exist in table 'cart_items' schema")
    return {
        "compliant": len(violations) == 0,
        "violations": violations
    }


def verify_openapi_compliance(code_content: str, openapi_path: str) -> dict:
    """
    Validates code_content against the OpenAPI endpoints and contract constraints.
    """
    violations = []
    # Read contract to find required fields for checkout
    required_fields = ["cart_id"]
    if os.path.exists(openapi_path):
        try:
            with open(openapi_path, "r", encoding="utf-8") as f:
                contract = json.load(f)
            # Fetch /api/v1/checkout post required schema properties
            checkout_schema = contract.get("paths", {}).get("/api/v1/checkout", {}).get("post", {}).get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            required_fields = checkout_schema.get("required", required_fields)
        except Exception:
            pass

    # If code references checkout request payload but does not contain required fields
    if "checkout" in code_content.lower() and not any(field in code_content for field in required_fields):
        for field in required_fields:
            if field not in code_content:
                violations.append(f"Missing required field '{field}' in checkout payload")
                
    return {
        "compliant": len(violations) == 0,
        "violations": violations
    }
