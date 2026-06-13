import os
import sys
import logging
import json

# Ensure root path is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.mcp_client import MCPClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    db_url = "postgresql://postgres:postgres@localhost:5432/wellactually"
    client = MCPClient("npx", ["-y", "@modelcontextprotocol/server-postgres", db_url])
    
    try:
        client.start()
        print("MCP client started successfully!")
        
        # Call query tool with correct 'sql' argument name
        res = client.call_tool("query", {
            "sql": "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public';"
        })
        print("Query Result:")
        print(json.dumps(res, indent=2))
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
