import json
import logging
import os
import re

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
        Tracks per-reviewer votes and generates structured summaries.
        """
        self.max_rounds = max_rounds
        self.rounds = {}  # Maps pr_id -> count of failed/disagreement rounds
        self.total_rounds = {}  # Maps pr_id -> total rounds attempted
        self.votes = {}   # Maps pr_id -> [{reviewer, role, verdict, round, domain}]

    def record_vote(self, pr_id: str, reviewer_name: str, role: str, verdict: str, round_num: int, domain: str = ""):
        """Record an individual reviewer's vote for a given round."""
        if pr_id not in self.votes:
            self.votes[pr_id] = []
        self.votes[pr_id].append({
            "reviewer": reviewer_name,
            "role": role,
            "verdict": verdict,
            "round": round_num,
            "domain": domain
        })

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
        if pr_id not in self.total_rounds:
            self.total_rounds[pr_id] = 0

        self.total_rounds[pr_id] += 1

        if outcome == "approved":
            return {
                "is_deadlocked": False,
                "action": "merge"
            }
        
        # Increment failure count on disagreement
        self.rounds[pr_id] += 1
        
        if self.rounds[pr_id] >= self.max_rounds:
            return {
                "is_deadlocked": True,
                "action": "hitl_escalation"
            }
        else:
            return {
                "is_deadlocked": False,
                "action": "continue"
            }

    def get_summary(self, pr_id: str) -> dict:
        """Return structured summary for the post-debate analytics card."""
        votes = self.votes.get(pr_id, [])
        failed_votes = [v for v in votes if v["verdict"] == "failed"]
        passed_votes = [v for v in votes if v["verdict"] == "passed"]
        
        # Group rejections by reviewer
        rejections_by_reviewer = {}
        for v in failed_votes:
            key = v["reviewer"]
            if key not in rejections_by_reviewer:
                rejections_by_reviewer[key] = {"role": v["role"], "domain": v["domain"], "count": 0}
            rejections_by_reviewer[key]["count"] += 1

        return {
            "total_rounds": self.total_rounds.get(pr_id, 0),
            "total_votes": len(votes),
            "rejections": len(failed_votes),
            "approvals": len(passed_votes),
            "rejections_by_reviewer": rejections_by_reviewer,
            "is_deadlocked": self.rounds.get(pr_id, 0) >= self.max_rounds,
            "votes": votes
        }


class TelemetryScanner:
    def __init__(self, log_path: str):
        """
        Initializes the scanner with the target JSON log path.
        """
        self.log_path = log_path

    def scan_leaks(self) -> list[dict]:
        """
        Scans logs for all WARNING and ERROR level entries as potential anomalies.
        Logs a warning alert and returns all matching log entries.
        """
        self.logs = []
        if not os.path.exists(self.log_path):
            logger.error(f"Log file not found at: {self.log_path}")
            return self.logs

        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                self.logs = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON logs at {self.log_path}: {e}")
            return []

        anomalies = []
        for entry in self.logs:
            # Match all WARNING and ERROR level entries as potential anomalies
            if entry.get("level") in ("WARNING", "ERROR"):
                logger.warning(
                    f"[ALERT] [Telemetry Watchdog] Anomaly detected in {entry.get('service', 'unknown-service')}! "
                    f"Message: {entry.get('message', '')} | Timestamp: {entry.get('timestamp')}"
                )
                anomalies.append(entry)

        return anomalies


def _parse_schema_columns(schema_sql: str) -> dict:
    """
    Extract column names from CREATE TABLE statements in a .sql file.
    Returns {table_name: set(column_names)}.
    """
    tables = {}
    for match in re.finditer(
        r"CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);",
        schema_sql, re.IGNORECASE | re.DOTALL
    ):
        table = match.group(1).lower()
        cols = set()
        for line in match.group(2).split("\n"):
            line = line.strip().rstrip(",")
            if line and not re.match(
                r"^(--|CHECK|UNIQUE|REFERENCES|PRIMARY|FOREIGN|CONSTRAINT)",
                line, re.IGNORECASE
            ):
                token = line.split()[0]
                if token.isidentifier():
                    cols.add(token.lower())
        tables[table] = cols
    return tables


def _extract_insert_columns(code_content: str) -> list:
    """
    Extract (table, [columns]) tuples from INSERT INTO statements in code.
    """
    results = []
    for match in re.finditer(
        r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)",
        code_content, re.IGNORECASE
    ):
        table = match.group(1).lower()
        cols = [c.strip().strip("'\"").lower() for c in match.group(2).split(",")]
        results.append((table, cols))
    return results


def _extract_select_columns(code_content: str) -> list:
    """
    Extract (table, [columns]) tuples from SELECT ... FROM statements in code.
    Skips SELECT * since we can't validate wildcard column access.
    """
    results = []
    for match in re.finditer(
        r"SELECT\s+(.+?)\s+FROM\s+(\w+)",
        code_content, re.IGNORECASE
    ):
        cols_str = match.group(1).strip()
        table = match.group(2).lower()
        if cols_str == '*':
            continue  # Can't validate SELECT *
        cols = [c.strip().strip("'\"").lower() for c in cols_str.split(",")]
        results.append((table, cols))
    return results


def verify_schema_compliance(code_content: str, schema_path: str) -> dict:
    """
    Validates code_content against the PostgreSQL schema boundaries.
    Parses INSERT INTO and SELECT statements from code and diffs column names
    against the actual CREATE TABLE definitions in the schema file.
    """
    violations = []

    # Parse the real schema
    schema_columns = {}
    if not os.path.exists(schema_path):
        return {
            "compliant": False,
            "violations": [f"Schema file not found: {schema_path}"]
        }
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    if not schema_sql.strip():
        return {
            "compliant": False,
            "violations": ["Schema file is empty"]
        }
    schema_columns = _parse_schema_columns(schema_sql)

    # Parse INSERT statements from the code
    inserts = _extract_insert_columns(code_content)
    for table, code_cols in inserts:
        if table in schema_columns:
            for col in code_cols:
                if col not in schema_columns[table]:
                    violations.append(f"Column '{col}' does not exist in table '{table}' schema")

    # Parse SELECT statements from the code
    selects = _extract_select_columns(code_content)
    for table, code_cols in selects:
        if table in schema_columns:
            for col in code_cols:
                if col not in schema_columns[table]:
                    violations.append(f"Column '{col}' does not exist in table '{table}' schema")

    return {
        "compliant": len(violations) == 0,
        "violations": violations
    }


def verify_openapi_compliance(code_content: str, openapi_path: str) -> dict:
    """
    Validates code_content against the OpenAPI endpoints and contract constraints.
    Parses required fields from the spec and checks that code includes them.
    """
    violations = []
    required_fields = ["cart_id"]
    
    if openapi_path and os.path.exists(openapi_path):
        try:
            with open(openapi_path, "r", encoding="utf-8") as f:
                contract = json.load(f)
            checkout_schema = (contract.get("paths", {})
                .get("/api/v1/checkout", {})
                .get("post", {})
                .get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {}))
            required_fields = checkout_schema.get("required", required_fields)
        except Exception as e:
            logger.warning(f"Failed to parse OpenAPI spec at {openapi_path}: {e}")

    # Check if code references checkout but omits required fields
    if "checkout" in code_content.lower():
        for field in required_fields:
            if field not in code_content:
                violations.append(f"Missing required field '{field}' in checkout payload")
                
    return {
        "compliant": len(violations) == 0,
        "violations": violations
    }


# Sensitive financial columns that require RBAC validation
RBAC_SENSITIVE_COLUMNS = {
    "billing_profiles": {"spending_limit_usd", "risk_classification", "payment_method_token"},
    "users": {"password_hash"},
    "transaction_audit_logs": {"risk_score", "ip_address"},
}

# Weak patterns — client-side if/else guards, NOT real RBAC middleware
RBAC_WEAK_PATTERNS = [
    r"role\s*==",           # if role == "admin"
    r"role\s+not\s+in",     # if role not in [...]
    r"role\s+in\s+\[",      # if role in ["admin"]
    r"user_role",           # user_role variable check
    r"\.role\b",            # user.role check
    r"is_admin",            # is_admin flag
]

# Strong patterns — actual RBAC middleware, decorators, or access-control functions
RBAC_STRONG_PATTERNS = [
    r"@requires_role",          # decorator pattern
    r"@require_role",           # decorator pattern (alternate)
    r"rbac\.check",             # middleware call
    r"rbac\.verify",            # middleware verify
    r"check_access\(",          # access control function
    r"verify_permission",       # permission verification
    r"authorization_middleware", # middleware reference
    r"has_permission\(",        # permission check function
    r"check_role\(",            # role check function call
    r"verify_role\(",           # role verify function call
]


def verify_rbac_compliance(code_content: str) -> dict:
    """
    Validates that code accessing sensitive financial columns includes proper
    RBAC middleware — not just client-side if/else guards.

    Tiered enforcement:
    - No RBAC at all → violation (direct access)
    - Weak RBAC (if role == ...) → violation (insufficient, needs middleware)
    - Strong RBAC (@requires_role, rbac.check) → compliant
    """
    violations = []

    code_lower = code_content.lower()
    for table, sensitive_cols in RBAC_SENSITIVE_COLUMNS.items():
        for col in sensitive_cols:
            if col in code_lower and table in code_lower:
                has_strong = any(re.search(p, code_content, re.IGNORECASE) for p in RBAC_STRONG_PATTERNS)
                if has_strong:
                    continue  # Proper RBAC middleware detected

                has_weak = any(re.search(p, code_content, re.IGNORECASE) for p in RBAC_WEAK_PATTERNS)
                if has_weak:
                    violations.append(
                        f"Access to '{table}.{col}' uses a client-side role guard instead of "
                        f"RBAC middleware. Financial columns require @requires_role decorator "
                        f"or rbac.check_access() middleware — client-side if/else guards are "
                        f"insufficient for production access control."
                    )
                else:
                    violations.append(
                        f"Direct access to '{table}.{col}' without RBAC role verification. "
                        f"Financial columns require role-based access control checks."
                    )

    return {
        "compliant": len(violations) == 0,
        "violations": violations
    }
