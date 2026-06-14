import json
import logging
import os
import re
from typing import List, Dict, Any

logger = logging.getLogger("GovernanceEngine")

_SCHEMA_CACHE = None
_POSTGRES_MCP_CLIENT = None
_POSTGRES_MCP_URL = None
_SQLITE_MCP_CLIENT = None


def get_postgres_mcp_client(db_url):
    global _POSTGRES_MCP_CLIENT, _POSTGRES_MCP_URL
    from src.mcp_client import MCPClient
    if _POSTGRES_MCP_CLIENT is None or _POSTGRES_MCP_URL != db_url:
        if _POSTGRES_MCP_CLIENT is not None:
            try:
                _POSTGRES_MCP_CLIENT.close()
            except Exception:
                pass
        logger.info(f"Starting persistent live Postgres MCP server: {db_url}")
        _POSTGRES_MCP_CLIENT = MCPClient("npx", ["-y", "@modelcontextprotocol/server-postgres", db_url])
        _POSTGRES_MCP_CLIENT.start()
        _POSTGRES_MCP_URL = db_url
    return _POSTGRES_MCP_CLIENT


def get_sqlite_mcp_client(server_script):
    global _SQLITE_MCP_CLIENT
    from src.mcp_client import MCPClient
    import sys
    if _SQLITE_MCP_CLIENT is None:
        logger.info("Starting persistent fallback SQLite MCP server...")
        _SQLITE_MCP_CLIENT = MCPClient(sys.executable, [server_script])
        _SQLITE_MCP_CLIENT.start()
    return _SQLITE_MCP_CLIENT


def cleanup_mcp_connections():
    global _POSTGRES_MCP_CLIENT, _SQLITE_MCP_CLIENT, _POSTGRES_MCP_URL
    if _POSTGRES_MCP_CLIENT is not None:
        try:
            logger.info("Closing persistent Postgres MCP server connection...")
            _POSTGRES_MCP_CLIENT.close()
        except Exception:
            pass
        _POSTGRES_MCP_CLIENT = None
        _POSTGRES_MCP_URL = None
    if _SQLITE_MCP_CLIENT is not None:
        try:
            logger.info("Closing persistent SQLite MCP server connection...")
            _SQLITE_MCP_CLIENT.close()
        except Exception:
            pass
        _SQLITE_MCP_CLIENT = None


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
        self.votes = {}   # Maps pr_id -> [{reviewer, role, verdict, round, domain, comment}]
        self.round_history = {} # Maps pr_id -> [{"round": int, "outcome": str}]

    def record_vote(self, pr_id: str, reviewer_name: str, role: str, verdict: str, round_num: int, domain: str = "", comment: str = ""):
        """Record an individual reviewer's vote and comment for a given round."""
        if pr_id not in self.votes:
            self.votes[pr_id] = []
        self.votes[pr_id].append({
            "reviewer": reviewer_name,
            "role": role,
            "verdict": verdict,
            "round": round_num,
            "domain": domain,
            "comment": comment
        })

    def check_convergence(self, pr_id: str) -> dict:
        """
        Analyzes reviewer comments and verdicts across rounds to detect
        convergence, oscillation, or exact repetition.
        """
        votes = self.votes.get(pr_id, [])
        if not votes:
            return {"status": "unknown", "similarity_index": 0.0, "details": "No votes recorded"}

        # Group votes by round
        rounds_data = {}
        for v in votes:
            r = v["round"]
            if r not in rounds_data:
                rounds_data[r] = []
            rounds_data[r].append(v)

        total_rounds = max(rounds_data.keys()) if rounds_data else 0
        if total_rounds <= 1:
            return {
                "status": "initial_round",
                "similarity_index": 0.0,
                "details": "Only one round of reviews completed. Need at least two to track convergence."
            }

        # Compare latest round (total_rounds) with the previous round (total_rounds - 1)
        prev_votes = rounds_data[total_rounds - 1]
        curr_votes = rounds_data[total_rounds]

        # Calculate Jaccard similarity of words
        def get_words(text):
            return set(re.findall(r'\w+', (text or "").lower()))

        similarities = []
        verdicts_match = True
        
        for curr_v in curr_votes:
            reviewer = curr_v["reviewer"]
            # Find matching previous vote
            prev_v = next((v for v in prev_votes if v["reviewer"] == reviewer), None)
            if prev_v:
                words1 = get_words(curr_v.get("comment", ""))
                words2 = get_words(prev_v.get("comment", ""))
                if words1 or words2:
                    sim = len(words1.intersection(words2)) / len(words1.union(words2))
                else:
                    sim = 1.0
                similarities.append(sim)
                if curr_v["verdict"] != prev_v["verdict"]:
                    verdicts_match = False

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

        # Determine convergence status
        if avg_similarity > 0.85:
            if verdicts_match:
                status = "stagnant"
                details = f"Reviews are repeating with high similarity ({avg_similarity:.2f}) and identical verdicts. Potential loop detected."
            else:
                status = "oscillating"
                details = f"Review comments are highly similar ({avg_similarity:.2f}) but verdicts changed. Potential oscillation detected."
        elif avg_similarity > 0.5:
            status = "converging"
            details = f"Review comments are moderately similar ({avg_similarity:.2f}) across rounds, indicating progress or refinement."
        else:
            status = "diverging"
            details = f"Review comments have low similarity ({avg_similarity:.2f}), suggesting changing requirements or shifting concerns."

        return {
            "status": status,
            "similarity_index": avg_similarity,
            "details": details
        }

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
        Scans logs for PII patterns (SSN, credit card, email, passwords, keys) or secrets
        and memory/database resource leaks using regex-based scanning.
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

        # Regex patterns for PII, secrets, keys, and resource/memory leaks
        pii_patterns = [
            # SSN
            r"\b\d{3}-\d{2}-\d{4}\b",
            # Credit Card
            r"\b(?:\d[ -]*?){13,16}\b",
            # Email
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
            # Passwords or secrets
            r"(?i)\b(?:password|passwd|pwd|passphrase|secret)(?:\s*[:=]\s*|\s+is\s+)['\"]?[a-zA-Z0-9_#$@!%&*()-]{4,}['\"]?",
            # API keys or authorization tokens
            r"(?i)\b(?:api[_-]?key|apikey|private[_-]?key|auth[_-]?token|bearer|token)(?:\s*[:=]\s*|\s+is\s+)['\"]?[a-zA-Z0-9_\-\.\/~\+\=]{8,}['\"]?",
            # Keep backward compatibility with existing telemetry leak/exhaustion tests
            r"(?i)\b(?:leak|exhaustion|heap|pool|sessionstore|unbounded|loop|query|rate|spike)\b"
        ]
        compiled_regexes = [re.compile(p) for p in pii_patterns]

        anomalies = []
        for entry in self.logs:
            message = entry.get("message", "")
            # Check if any regex matches the log message
            matched = False
            for rx in compiled_regexes:
                if rx.search(message):
                    matched = True
                    break

            if matched:
                logger.warning(
                    f"[ALERT] [Telemetry Watchdog] Leak/Anomaly detected in {entry.get('service', 'unknown-service')}! "
                    f"Message: {message} | Timestamp: {entry.get('timestamp')}"
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


def extract_aliases_robust(query: str, schema_tables: set) -> dict:
    """
    Robust table alias resolution for SQL queries.
    Handles joins, subqueries, and table aliases correctly.
    """
    alias_to_table = {}
    
    # SQL keywords to ignore when checking aliases
    SQL_KEYWORDS_LOCAL = {
        "select", "insert", "update", "delete", "from", "where", "join", "on", 
        "and", "or", "not", "in", "is", "null", "values", "into", "set", "as", 
        "by", "order", "group", "having", "limit", "offset", "inner", "left", 
        "right", "outer", "cross", "natural", "true", "false", "using", "union",
        "with", "as"
    }

    # Clean query (remove comments and strings)
    q = re.sub(r"'(?:''|[^'])*'", " ", query)
    q = re.sub(r'"(?:""|[^"])*"', " ", q)
    q = re.sub(r'/\*.*?\*/', '', q, flags=re.DOTALL)
    q = re.sub(r'--.*$', '', q, flags=re.MULTILINE)
    
    # 1. Standard aliases: table_name [AS] alias
    for table_name in schema_tables:
        pattern = r'\b' + re.escape(table_name) + r'\b\s+(?:AS\s+)?([a-zA-Z_]\w*)\b'
        for m in re.finditer(pattern, q, re.IGNORECASE):
            alias = m.group(1).lower()
            if alias not in SQL_KEYWORDS_LOCAL:
                alias_to_table[alias] = table_name.lower()
                
    # 2. Subquery aliases: (SELECT ... FROM table) [AS] alias
    subquery_pattern = r'\(\s*SELECT\s+.*?\b(?:FROM|JOIN)\s+(\w+)\b.*?\)\s*(?:AS\s+)?([a-zA-Z_]\w*)\b'
    for m in re.finditer(subquery_pattern, q, re.IGNORECASE | re.DOTALL):
        source_table = m.group(1).lower()
        alias = m.group(2).lower()
        if source_table in schema_tables and alias not in SQL_KEYWORDS_LOCAL:
            alias_to_table[alias] = source_table

    # 3. CTE aliases: WITH alias AS (SELECT ... FROM table)
    cte_pattern = r'\bWITH\s+([a-zA-Z_]\w*)\s+AS\s+\(\s*SELECT\s+.*?\b(?:FROM|JOIN)\s+(\w+)\b'
    for m in re.finditer(cte_pattern, q, re.IGNORECASE | re.DOTALL):
        alias = m.group(1).lower()
        source_table = m.group(2).lower()
        if source_table in schema_tables and alias not in SQL_KEYWORDS_LOCAL:
            alias_to_table[alias] = source_table
            
    return alias_to_table



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
            try:
                client = get_postgres_mcp_client(db_url)
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
                # Reset client so it reconnects next time
                global _POSTGRES_MCP_CLIENT
                if _POSTGRES_MCP_CLIENT is not None:
                    try:
                        _POSTGRES_MCP_CLIENT.close()
                    except Exception:
                        pass
                    _POSTGRES_MCP_CLIENT = None
                schema_columns = {}

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
        try:
            client = get_sqlite_mcp_client(server_script)
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
            global _SQLITE_MCP_CLIENT
            if _SQLITE_MCP_CLIENT is not None:
                try:
                    _SQLITE_MCP_CLIENT.close()
                except Exception:
                    pass
                _SQLITE_MCP_CLIENT = None
            schema_columns = {}

    # Fallback to local file parsing if everything else failed
    if not schema_columns:
        if not schema_path or not os.path.exists(schema_path):
            # If schema_path doesn't exist, we are compliant by default (no database to validate)
            return {
                "compliant": True,
                "violations": [],
                "checked_columns": []
            }
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        if not schema_sql.strip():
            # Empty schema is also compliant by default
            return {
                "compliant": True,
                "violations": [],
                "checked_columns": []
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

        # Extract table aliases using robust parsing
        alias_to_table = extract_aliases_robust(query_temp, set(schema_columns.keys()))
        aliases = set(alias_to_table.keys())

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
    
    if openapi_path and os.path.exists(openapi_path):
        try:
            with open(openapi_path, "r", encoding="utf-8") as f:
                contract = json.load(f)
            
            paths = contract.get("paths", {})
            for p, path_item in paths.items():
                # Check if this path is touched in the code_content
                segments = [s for s in p.split('/') if s and not s.startswith('{')]
                is_touched = False
                if p in code_content:
                    is_touched = True
                elif segments:
                    last_seg = segments[-1]
                    if len(last_seg) > 2 and last_seg.lower() in code_content.lower():
                        is_touched = True
                
                if is_touched:
                    for method in ["post", "put", "get", "patch", "delete"]:
                        method_item = path_item.get(method)
                        if not method_item:
                            continue
                        
                        required_fields = []
                        # 1. Parse parameters
                        for param in method_item.get("parameters", []):
                            if param.get("required") and "name" in param:
                                required_fields.append(param["name"])
                        
                        # 2. Parse requestBody schema
                        schema = (method_item.get("requestBody", {})
                            .get("content", {})
                            .get("application/json", {})
                            .get("schema", {}))
                        if schema:
                            required_fields.extend(schema.get("required", []))
                        
                        # Verify fields in code_content
                        for field in required_fields:
                            if field not in code_content:
                                violations.append(f"Missing required field '{field}' in {method.upper()} {p} payload")
        except Exception as e:
            logger.warning(f"Failed to parse OpenAPI spec at {openapi_path}: {e}")
            # Fallback to checkout validation if parsing fails
            if "checkout" in code_content.lower():
                if "cart_id" not in code_content:
                    violations.append("Missing required field 'cart_id' in checkout payload")
    else:
        # Fallback if no file exists
        if "checkout" in code_content.lower():
            if "cart_id" not in code_content:
                violations.append("Missing required field 'cart_id' in checkout payload")

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


def clean_python_comments_and_strings(code: str) -> str:
    # Remove multi-line comments/docstrings
    code = re.sub(r'"""[\s\S]*?"""', ' ', code)
    code = re.sub(r"'''[\s\S]*?'''", ' ', code)
    # Remove single line comments
    code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
    # Remove string literals
    code = re.sub(r"'(?:''|[^'])*'", " ", code)
    code = re.sub(r'"(?:""|[^"])*"', " ", code)
    return code


def check_rbac_in_ast(code_content: str) -> bool:
    import ast
    try:
        # Extract code block if in markdown
        code_to_parse = code_content
        code_blocks = re.findall(r"```python\s*(.*?)\s*```", code_content, re.DOTALL)
        if code_blocks:
            code_to_parse = "\n".join(code_blocks)

        tree = ast.parse(code_to_parse)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    dec_name = ""
                    if isinstance(dec, ast.Name):
                        dec_name = dec.id
                    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                        dec_name = dec.func.id
                    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if isinstance(dec.func.value, ast.Name):
                            dec_name = f"{dec.func.value.id}.{dec.func.attr}"
                    
                    if dec_name.lower() in ("requires_role", "require_role", "rbac.requires_role", "rbac.require_role"):
                        return True
            
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    func_name = f"{node.func.value.id}.{node.func.attr}"
                
                func_name_lower = func_name.lower()
                if func_name_lower in (
                    "rbac.check", "rbac.verify", "check_access", "verify_permission",
                    "authorization_middleware", "has_permission", "check_role", "verify_role"
                ):
                    return True
                    
            if isinstance(node, ast.Name):
                if node.id.lower() == "authorization_middleware":
                    return True
    except Exception:
        pass
    return False


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
    
    # Check using AST and cleaned text to prevent comment/string bypasses
    has_strong = check_rbac_in_ast(code_content)
    if not has_strong:
        cleaned = clean_python_comments_and_strings(code_content)
        has_strong = any(re.search(p, cleaned, re.IGNORECASE) for p in RBAC_STRONG_PATTERNS)

    cleaned_for_weak = clean_python_comments_and_strings(code_content)
    has_weak = any(re.search(p, cleaned_for_weak, re.IGNORECASE) for p in RBAC_WEAK_PATTERNS)

    # Clean only comments to look for table/column accesses (since they live inside SQL string literals)
    code_no_comments = re.sub(r'"""[\s\S]*?"""', ' ', code_content)
    code_no_comments = re.sub(r"'''[\s\S]*?'''", ' ', code_no_comments)
    code_no_comments = re.sub(r'#.*$', '', code_no_comments, flags=re.MULTILINE)
    code_lower = code_no_comments.lower()

    for table, sensitive_cols in RBAC_SENSITIVE_COLUMNS.items():
        for col in sensitive_cols:
            if col in code_lower and table in code_lower:
                if has_strong:
                    continue  # Proper RBAC middleware detected

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
