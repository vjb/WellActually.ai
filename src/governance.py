import json
import logging
import os
import re
from typing import List, Dict, Any

logger = logging.getLogger("GovernanceEngine")

_SCHEMA_CACHE = None


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


def triage_pr(diff_files: List[str], codeowners_rules: Dict[str, Any]) -> Dict[str, Any]:
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
        self.round_history = {} # Maps pr_id -> [{"round": int, "outcome": str}]

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
        if pr_id not in self.round_history:
            self.round_history[pr_id] = []

        self.total_rounds[pr_id] += 1

        round_num = self.total_rounds[pr_id]
        round_outcome = "approved" if outcome == "approved" else "rejected"
        self.round_history[pr_id].append({
            "round": round_num,
            "outcome": round_outcome
        })

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
            "votes": votes,
            "round_history": self.round_history.get(pr_id, [])
        }


class TelemetryScanner:
    def __init__(self, log_path: str):
        """
        Initializes the scanner with the target JSON log path.
        """
        self.log_path = log_path

    def scan_leaks(self) -> List[Dict[str, Any]]:
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
    # Clean SQL comments to prevent matching commented-out tables/columns
    schema_sql_clean = re.sub(r'/\*.*?\*/', '', schema_sql, flags=re.DOTALL)
    schema_sql_clean = re.sub(r'--.*$', '', schema_sql_clean, flags=re.MULTILINE)

    for match in re.finditer(
        r"CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);",
        schema_sql_clean, re.IGNORECASE | re.DOTALL
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
    Parses Python AST to extract all SQL query strings, cleans comments,
    resolves referenced tables, and validates select columns and other query 
    tokens against the actual CREATE TABLE schemas.
    """
    import ast
    from src.config import config
    from src.mcp_client import MCPClient

    global _SCHEMA_CACHE
    violations = []
    schema_columns = {}

    use_real = config.get("USE_REAL_DB", default="false").lower() == "true"
    db_url = config.get("DATABASE_URL")
    postgres_success = False

    if use_real and db_url:
        if _SCHEMA_CACHE is not None:
            schema_columns = _SCHEMA_CACHE
            postgres_success = True
            logger.info("Using cached schema columns from live PostgreSQL database.")
        else:
            logger.info(f"Connecting to live Postgres MCP server for schema checks: {db_url}")
            client = MCPClient("npx", ["-y", "@modelcontextprotocol/server-postgres", db_url])
            try:
                client.start()
                res = client.call_tool("query", {
                    "sql": "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public';"
                })
                content = res.get("content", [])
                if content and content[0].get("type") == "text":
                    text_data = content[0].get("text", "[]")
                    records = json.loads(text_data)
                    for rec in records:
                        table = rec.get("table_name").lower()
                        column = rec.get("column_name").lower()
                        if table not in schema_columns:
                            schema_columns[table] = set()
                        schema_columns[table].add(column)
                _SCHEMA_CACHE = schema_columns
                postgres_success = True
                logger.info(f"Successfully loaded and cached {len(schema_columns)} tables from live PostgreSQL database via MCP.")
            except Exception as e:
                logger.error(f"Failed to fetch schema from live Postgres MCP server: {e}")
                schema_columns = {}
            finally:
                client.close()

        if not postgres_success or not schema_columns:
            return {
                "compliant": False,
                "violations": ["Failed to connect or retrieve schema from live PostgreSQL database via MCP. (No fallbacks allowed when USE_REAL_DB=true)"],
                "checked_columns": []
            }

    # Fallback to SQLite MCP server only if PostgreSQL checks are disabled (USE_REAL_DB=false)
    if not use_real:
        logger.info("Connecting to fallback SQLite MCP server for schema checks...")
        import sys
        server_script = os.path.join(os.path.dirname(__file__), "mcp_sqlite_server.py")
        client = MCPClient(sys.executable, [server_script])
        try:
            client.start()
            res = client.call_tool("query", {
                "sql": "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public';"
            })
            content = res.get("content", [])
            if content and content[0].get("type") == "text":
                text_data = content[0].get("text", "[]")
                records = json.loads(text_data)
                for rec in records:
                    table = rec.get("table_name").lower()
                    column = rec.get("column_name").lower()
                    if table not in schema_columns:
                        schema_columns[table] = set()
                    schema_columns[table].add(column)
            logger.info(f"Successfully loaded {len(schema_columns)} tables from fallback SQLite MCP server.")
        except Exception as e:
            logger.warning(f"Failed to fetch schema from fallback SQLite MCP server, falling back to local file. Reason: {e}")
            schema_columns = {}
        finally:
            client.close()

    # Fallback to local file parsing if everything else failed
    if not schema_columns:
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

    # 1. Extract all SQL string literals from code
    sql_queries = []
    
    # Extract Python code from markdown code block if present
    code_to_parse = code_content
    code_blocks = re.findall(r"```python\s*(.*?)\s*```", code_content, re.DOTALL)
    if code_blocks:
        code_to_parse = "\n".join(code_blocks)

    try:
        tree = ast.parse(code_to_parse)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value.strip()
                # Match SELECT, INSERT, UPDATE, DELETE queries
                if any(k in val.upper() for k in ["SELECT", "INSERT INTO", "UPDATE", "DELETE FROM"]):
                    sql_queries.append(val)
    except Exception:
        # Fallback to lines/regex extraction if the snippet is not valid Python
        sql_queries = []
        for line in code_content.splitlines():
            line_upper = line.upper()
            if any(k in line_upper for k in ["SELECT", "INSERT INTO", "UPDATE", "DELETE FROM"]):
                sql_queries.append(line)
        if not sql_queries:
            sql_queries = [code_to_parse]

    # SQL keywords to ignore when checking column tokens
    SQL_KEYWORDS = {
        "select", "insert", "update", "delete", "from", "where", "join", "on", 
        "and", "or", "not", "in", "is", "null", "values", "into", "set", "as", 
        "by", "order", "group", "having", "limit", "offset", "inner", "left", 
        "right", "outer", "cross", "natural", "true", "false", "uuid", "uuid_generate_v4",
        "primary", "key", "foreign", "references", "table", "create", "drop", "alter"
    }

    checked_columns_list = []
    seen_checked = set()

    for query in sql_queries:
        # Clean comments from the query
        query_clean = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        query_clean = re.sub(r'--.*$', '', query_clean, flags=re.MULTILINE)

        # Identify which tables are referenced in this query
        referenced_tables = []
        for table_name in schema_columns.keys():
            if re.search(r'\b' + re.escape(table_name) + r'\b', query_clean, re.IGNORECASE):
                referenced_tables.append(table_name)

        if not referenced_tables:
            continue

        # Clean string literals to prevent checking strings (like 'active', 'completed') as identifiers
        query_temp = re.sub(r"'(?:''|[^'])*'", " ", query_clean)
        query_temp = re.sub(r'"(?:""|[^"])*"', " ", query_temp)

        # Clean placeholders from query
        query_temp = re.sub(r'%[a-zA-Z]', ' ', query_temp)
        query_temp = re.sub(r'\$\d+', ' ', query_temp)
        query_temp = re.sub(r':\w+', ' ', query_temp)
        query_temp = re.sub(r'\?', ' ', query_temp)

        # Extract table aliases from FROM and JOIN clauses
        # e.g., "FROM billing_profiles bp" or "FROM billing_profiles AS bp"
        aliases = set()
        alias_to_table = {}
        for table_name in schema_columns.keys():
            matches = re.finditer(
                r'\b' + re.escape(table_name) + r'\b\s+(?:AS\s+)?([a-zA-Z_]\w*)\b',
                query_temp,
                re.IGNORECASE
            )
            for m in matches:
                alias = m.group(1).lower()
                if alias not in SQL_KEYWORDS:
                    aliases.add(alias)
                    alias_to_table[alias] = table_name

        # Check for INSERT columns
        insert_matches = list(re.finditer(r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)", query_clean, re.IGNORECASE))
        for match in insert_matches:
            target_table = match.group(1).lower()
            if target_table in schema_columns:
                # Extract columns
                cols = [c.strip().strip("'\"`").lower() for c in match.group(2).split(",")]
                for col in cols:
                    compliant = col in schema_columns[target_table]
                    if (target_table, col) not in seen_checked:
                        seen_checked.add((target_table, col))
                        checked_columns_list.append({
                            "table": target_table,
                            "column": col,
                            "compliant": compliant
                        })
                    if not compliant:
                        violations.append(f"Column '{col}' does not exist in table '{target_table}' schema")

        # Check for SELECT columns (explicit list, ignore SELECT *)
        select_matches = list(re.finditer(r"SELECT\s+(.+?)\s+FROM\s+", query_clean, re.IGNORECASE | re.DOTALL))
        for match in select_matches:
            cols_str = match.group(1).strip()
            if cols_str == "*":
                continue
            
            # Split select list, stripping aliases, expressions, and functions
            # e.g., bp.spending_limit_usd -> spending_limit_usd
            # e.g., COUNT(*) -> skip/ignore
            # e.g., bp.spending_limit_usd AS limit -> spending_limit_usd
            select_items = cols_str.split(",")
            for item in select_items:
                item_clean = item.strip()
                # Ignore SQL function calls like COUNT(*), MAX(...)
                if "(" in item_clean:
                    continue
                # Remove AS alias
                item_clean = re.split(r'\s+AS\s+', item_clean, flags=re.IGNORECASE)[0].strip()
                # Remove trailing words if alias defined without AS: e.g. "bp.spending_limit_usd limit"
                item_clean = item_clean.split()[-1] if len(item_clean.split()) > 1 else item_clean
                
                # Strip qualifiers: e.g. bp.spending_limit_usd -> spending_limit_usd
                qualifier = None
                if "." in item_clean:
                    parts = item_clean.split(".")
                    qualifier = parts[0].strip().strip("'\"`").lower()
                    item_clean = parts[-1]
                
                col_name = item_clean.strip("'\"`").lower()
                
                # Special exceptions for identifiers like *
                if col_name == "*" or not col_name.isidentifier():
                    continue

                # Determine which table this column is associated with
                target_table = None
                if qualifier:
                    if qualifier in schema_columns:
                        target_table = qualifier
                    elif qualifier in alias_to_table:
                        target_table = alias_to_table[qualifier]
                
                col_found = False
                if target_table:
                    if col_name in schema_columns[target_table]:
                        col_found = True
                else:
                    # Search referenced tables
                    for tbl in referenced_tables:
                        if col_name in schema_columns[tbl]:
                            col_found = True
                            target_table = tbl
                            break
                    if not target_table and referenced_tables:
                        target_table = referenced_tables[0]

                if target_table:
                    if (target_table, col_name) not in seen_checked:
                        seen_checked.add((target_table, col_name))
                        checked_columns_list.append({
                            "table": target_table,
                            "column": col_name,
                            "compliant": col_found
                        })

                if not col_found:
                    # Report violation against the first referenced table
                    violations.append(f"Column '{col_name}' does not exist in table '{target_table or referenced_tables[0]}' schema")

        # Check WHERE, JOIN, and ORDER BY clauses for general token violations
        # Find all words/identifiers in the query that are NOT followed by a parenthesis
        all_words = re.findall(r'\b(?:([a-zA-Z_]\w*)\.)?([a-zA-Z_]\w*)\b(?!\s*\()', query_temp)
        for prefix, word in all_words:
            word_lower = word.lower()
            prefix_lower = prefix.lower() if prefix else ""
            
            if word_lower in SQL_KEYWORDS:
                continue
            if word_lower.isdigit() or not word_lower.isidentifier():
                continue
            if word_lower in schema_columns:  # Table name
                continue
            if word_lower in aliases:  # Table alias
                continue

            # Determine if this column exists in the database schema at all
            is_valid_db_column = False
            for tbl, cols in schema_columns.items():
                if word_lower in cols:
                    is_valid_db_column = True
                    break

            target_table = None
            col_found = False

            if prefix_lower:
                if prefix_lower in schema_columns:
                    target_table = prefix_lower
                    col_found = word_lower in schema_columns[prefix_lower]
                elif prefix_lower in alias_to_table:
                    target_table = alias_to_table[prefix_lower]
                    col_found = word_lower in schema_columns[target_table]
                else:
                    target_table = referenced_tables[0]
                    if is_valid_db_column:
                        col_found = any(word_lower in schema_columns[tbl] for tbl in referenced_tables)
                    else:
                        col_found = False
            else:
                target_table = referenced_tables[0]
                if is_valid_db_column:
                    col_found = any(word_lower in schema_columns[tbl] for tbl in referenced_tables)
                else:
                    col_found = False

            if target_table:
                if (target_table, word_lower) not in seen_checked:
                    seen_checked.add((target_table, word_lower))
                    checked_columns_list.append({
                        "table": target_table,
                        "column": word_lower,
                        "compliant": col_found
                    })

            if prefix_lower:
                if prefix_lower in schema_columns:
                    if word_lower not in schema_columns[prefix_lower]:
                        violations.append(f"Column '{word_lower}' does not exist in table '{prefix_lower}' schema")
                elif prefix_lower in alias_to_table:
                    target_table_act = alias_to_table[prefix_lower]
                    if word_lower not in schema_columns[target_table_act]:
                        violations.append(f"Column '{word_lower}' does not exist in table '{target_table_act}' schema")
                else:
                    if is_valid_db_column:
                        in_referenced = any(word_lower in schema_columns[tbl] for tbl in referenced_tables)
                        if not in_referenced:
                            violations.append(f"Column '{word_lower}' does not exist in table '{referenced_tables[0]}' schema")
                    else:
                        violations.append(f"Column '{word_lower}' does not exist in table '{referenced_tables[0]}' schema")
            else:
                if is_valid_db_column:
                    in_referenced = any(word_lower in schema_columns[tbl] for tbl in referenced_tables)
                    if not in_referenced:
                        violations.append(f"Column '{word_lower}' does not exist in table '{referenced_tables[0]}' schema")
                else:
                    violations.append(f"Column '{word_lower}' does not exist in table '{referenced_tables[0]}' schema")

    # De-duplicate violations while preserving order
    seen = set()
    deduped_violations = []
    for v in violations:
        if v not in seen:
            seen.add(v)
            deduped_violations.append(v)

    return {
        "compliant": len(deduped_violations) == 0,
        "violations": deduped_violations,
        "checked_columns": checked_columns_list
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
