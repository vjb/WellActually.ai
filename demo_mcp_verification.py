import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

# Ensure root path is in python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.governance import verify_schema_compliance, verify_openapi_compliance

console = Console()

def main():
    console.print(Panel(
        "[bold cyan]COMPONENT DEMO: MCP BOUNDED CONTEXT VERIFICATION[/bold cyan]\n"
        "[dim]Demonstrating Static Checks for PostgreSQL Schema and OpenAPI Contract Mismatches[/dim]",
        border_style="cyan",
        expand=False
    ))

    postgres_schema_path = "mock_infrastructure/postgres_schema.sql"
    openapi_contract_path = "mock_infrastructure/openapi_contract.json"

    # 1. Display Database Schema Layout
    if os.path.exists(postgres_schema_path):
        console.print("\n[bold yellow]PostgreSQL Table Schema Context (postgres_schema.sql)[/bold yellow]")
        with open(postgres_schema_path, "r", encoding="utf-8") as f:
            schema_content = f.read()
        console.print(Panel(Syntax(schema_content.strip(), "sql", theme="monokai", line_numbers=True), border_style="blue", expand=False))

    # 2. Display OpenAPI Contract Context
    if os.path.exists(openapi_contract_path):
        console.print("\n[bold yellow]OpenAPI Endpoint Contract Context (openapi_contract.json)[/bold yellow]")
        with open(openapi_contract_path, "r", encoding="utf-8") as f:
            openapi_content = f.read()
        console.print(Panel(Syntax(openapi_content.strip()[:600] + "\n... [truncated] ...", "json", theme="monokai"), border_style="blue", expand=False))

    # 3. Simulate Code Violation Scenarios
    console.print("\n[bold magenta]Running Static Bounded Context Checks...[/bold magenta]")

    # Scenario 1: Postgres Schema Violation
    violating_sql_code = """
def update_cart_item(cart_id, quantity):
    # Violation: discount_applied is not in postgres_schema.sql for cart_items
    query = "INSERT INTO cart_items (cart_id, product_id, discount_applied) VALUES (%s, 99, 0.25)"
    db.execute(query, (cart_id,))
"""
    console.print("\n[bold yellow]Test Case 1: Proposed Code with Database Schema Mismatch[/bold yellow]")
    console.print(Panel(Syntax(violating_sql_code.strip(), "python", theme="monokai"), title="Coder Proposal", border_style="yellow"))
    
    schema_check = verify_schema_compliance(violating_sql_code, postgres_schema_path)
    status_str = "[bold green]COMPLIANT[/bold green]" if schema_check["compliant"] else "[bold red]VIOLATED (BLOCKED)[/bold red]"
    console.print(f"MCP Schema Status: {status_str}")
    if not schema_check["compliant"]:
        console.print(f"Violations Found : [red]{schema_check['violations']}[/red]")

    # Scenario 2: OpenAPI Contract Violation
    violating_api_code = """
def checkout_cart(payload):
    # Violation: missing the required unique identifier 'cart_id' parameter in JSON payload
    data = {
        "payment_method_token": payload["token"]
    }
    return post("/api/v1/checkout", json=data)
"""
    console.print("\n[bold yellow]Test Case 2: Proposed Code with OpenAPI Payload Contract Mismatch[/bold yellow]")
    console.print(Panel(Syntax(violating_api_code.strip(), "python", theme="monokai"), title="Coder Proposal", border_style="yellow"))
    
    openapi_check = verify_openapi_compliance(violating_api_code, openapi_contract_path)
    status_str = "[bold green]COMPLIANT[/bold green]" if openapi_check["compliant"] else "[bold red]VIOLATED (BLOCKED)[/bold red]"
    console.print(f"MCP OpenAPI Status: {status_str}")
    if not openapi_check["compliant"]:
        console.print(f"Violations Found : [red]{openapi_check['violations']}[/red]")

if __name__ == "__main__":
    main()
