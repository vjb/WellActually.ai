import sys
import os
import json
import sqlite3
import re
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("mcp_sqlite_server")

def clean_postgres_to_sqlite(sql_content: str) -> str:
    """
    Clean PostgreSQL-specific DDL syntax to make it SQLite-compliant.
    """
    # Remove CREATE EXTENSION statements
    sql_content = re.sub(r'(?i)CREATE\s+EXTENSION\s+[^;]+;', '', sql_content)
    
    # Remove CREATE TYPE statements
    sql_content = re.sub(r'(?i)CREATE\s+TYPE\s+[^;]+;', '', sql_content)
    
    # Remove CREATE ROLE statements
    sql_content = re.sub(r'(?i)CREATE\s+ROLE\s+[^;]+;', '', sql_content)
    
    # Remove GRANT statements
    sql_content = re.sub(r'(?i)GRANT\s+[^;]+;', '', sql_content)
    
    # Replace UUID data type with TEXT
    sql_content = re.sub(r'\bUUID\b', 'TEXT', sql_content, flags=re.IGNORECASE)
    
    # Replace user_role custom type with VARCHAR(50)
    sql_content = re.sub(r'\buser_role\b', 'VARCHAR(50)', sql_content, flags=re.IGNORECASE)
    
    # Replace INET data type with TEXT
    sql_content = re.sub(r'\bINET\b', 'TEXT', sql_content, flags=re.IGNORECASE)
    
    # Replace JSONB data type with TEXT
    sql_content = re.sub(r'\bJSONB\b', 'TEXT', sql_content, flags=re.IGNORECASE)
    
    # Replace TIMESTAMP WITH TIME ZONE with TIMESTAMP
    sql_content = re.sub(r'\bTIMESTAMP\s+WITH\s+TIME\s+ZONE\b', 'TIMESTAMP', sql_content, flags=re.IGNORECASE)
    
    # Remove DEFAULT uuid_generate_v4() helper call
    sql_content = re.sub(r'DEFAULT\s+uuid_generate_v4\(\)', '', sql_content, flags=re.IGNORECASE)
    
    return sql_content

def main():
    logger.info("Starting SQLite Fallback Database MCP Server...")
    
    # Resolve the postgres_schema.sql path
    possible_paths = [
        "mock_infrastructure/postgres_schema.sql",
        os.path.join(os.path.dirname(__file__), "..", "mock_infrastructure", "postgres_schema.sql"),
        os.path.join(os.path.dirname(__file__), "mock_infrastructure", "postgres_schema.sql")
    ]
    schema_path = None
    for p in possible_paths:
        if os.path.exists(p):
            schema_path = p
            break
            
    if not schema_path:
        logger.error("Could not locate mock_infrastructure/postgres_schema.sql")
        sys.exit(1)
        
    logger.info(f"Reading PostgreSQL schema from {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        postgres_sql = f.read()
        
    cleaned_sql = clean_postgres_to_sqlite(postgres_sql)
    
    # Setup in-memory SQLite database
    db_conn = sqlite3.connect(":memory:")
    db_conn.execute("PRAGMA foreign_keys = ON;")
    
    # Execute the cleaned SQL DDL statements
    try:
        db_conn.executescript(cleaned_sql)
        logger.info("Successfully executed cleaned schema DDL in SQLite.")
    except Exception as e:
        logger.error(f"Failed to execute cleaned DDL in SQLite: {e}")
        logger.debug(f"Cleaned DDL attempted:\n{cleaned_sql}")
        sys.exit(1)
        
    # Create information_schema_columns table
    cursor = db_conn.cursor()
    cursor.execute("""
        CREATE TABLE information_schema_columns (
            table_schema TEXT,
            table_name TEXT,
            column_name TEXT
        );
    """)
    db_conn.commit()
    
    # Retrieve user tables and populate information_schema_columns
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'information_schema_columns';")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [row[1] for row in cursor.fetchall()]
        for col in columns:
            cursor.execute(
                "INSERT INTO information_schema_columns (table_schema, table_name, column_name) VALUES (?, ?, ?);",
                ("public", table, col)
            )
    db_conn.commit()
    logger.info(f"Populated information_schema_columns with columns from {len(tables)} tables.")
    
    # JSON-RPC request processing loop over stdin/stdout
    while True:
        line = sys.stdin.readline()
        if not line:
            logger.info("stdin EOF reached. Exiting server.")
            break
            
        line = line.strip()
        if not line:
            continue
            
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON-RPC payload: {line}, error: {e}")
            continue
            
        msg_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "sqlite-fallback-server",
                        "version": "1.0.0"
                    }
                }
            }
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        elif method == "notifications/initialized":
            logger.info("Handshake notifications/initialized received.")
            continue
            
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "query",
                            "description": "Execute a SQL query against the SQLite database",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "sql": {
                                        "type": "string",
                                        "description": "The SQL query to execute"
                                    }
                                },
                                "required": ["sql"]
                            }
                        }
                    ]
                }
            }
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if tool_name == "query":
                sql = arguments.get("sql", "")
                # Clean up query to redirect information_schema.columns to information_schema_columns
                sql_to_run = re.sub(
                    r'\binformation_schema\.columns\b',
                    'information_schema_columns',
                    sql,
                    flags=re.IGNORECASE
                )
                logger.info(f"Executing SQL query: {sql_to_run}")
                
                try:
                    cursor = db_conn.cursor()
                    cursor.execute(sql_to_run)
                    
                    col_names = [desc[0] for desc in cursor.description] if cursor.description else []
                    rows = cursor.fetchall()
                    
                    results = []
                    for row in rows:
                        results.append(dict(zip(col_names, row)))
                        
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(results)
                                }
                            ]
                        }
                    }
                except Exception as e:
                    logger.error(f"SQL error while executing query: {e}")
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32603,
                            "message": str(e)
                        }
                    }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            else:
                if msg_id is not None:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Tool '{tool_name}' not found"
                        }
                    }
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
        else:
            if msg_id is not None:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method '{method}' not found"
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

if __name__ == "__main__":
    main()
