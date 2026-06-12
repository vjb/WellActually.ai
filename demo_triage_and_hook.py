import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure root path is in python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.governance import parse_codeowners, triage_pr

console = Console()

def main():
    console.print(Panel(
        "[bold cyan]COMPONENT DEMO: COMPLIANCE TRIAGE & GIT HOOKS[/bold cyan]\n"
        "[dim]Demonstrating Zero-Trust Policy Interception and Local Hook Enforcement[/dim]",
        border_style="cyan",
        expand=False
    ))

    # 1. Load CODEOWNERS content
    codeowners_path = "mock_infrastructure/CODEOWNERS"
    if not os.path.exists(codeowners_path):
        console.print(f"[bold red]Error:[/bold red] CODEOWNERS file not found at {codeowners_path}")
        return

    with open(codeowners_path, "r", encoding="utf-8") as f:
        codeowners_content = f.read()

    rules = parse_codeowners(codeowners_content)

    # Display parsed rules in a Table
    rules_table = Table(title="Parsed CODEOWNERS Policies", show_header=True, header_style="bold magenta")
    rules_table.add_column("Path / Pattern", style="cyan")
    rules_table.add_column("Owner Pool", style="green")
    rules_table.add_column("High-Stakes Status", style="bold red")

    for pattern, rule in rules.items():
        high_stakes_str = "✓ YES (Forced HITL)" if rule["is_high_stakes"] else "✗ NO"
        rules_table.add_row(pattern, rule["owner"], high_stakes_str)
    
    console.print(rules_table)

    # 2. Simulate PR Changes Triage
    scenarios = [
        {
            "name": "Scenario A: Low-Stakes Cart Update",
            "files": ["src/cart/cart_service.py"]
        },
        {
            "name": "Scenario B: High-Stakes Authentication Modification",
            "files": ["src/auth/auth_service.py", "src/cart/cart_service.py"]
        },
        {
            "name": "Scenario C: High-Stakes Billing Update",
            "files": ["src/billing/billing_service.py"]
        }
    ]

    for sc in scenarios:
        console.print(f"\n[bold yellow]{sc['name']}[/bold yellow]")
        console.print(f"Modified Files: [magenta]{sc['files']}[/magenta]")
        
        triage_result = triage_pr(sc["files"], rules)
        
        status_color = "red" if triage_result["status"] == "PENDING_HUMAN_APPROVAL" else "green"
        console.print(f"Compliance Triage Status: [bold {status_color}]{triage_result['status']}[/bold {status_color}]")
        console.print(f"Required Approver Pools : [white]{triage_result['required_approvals']}[/white]")
        
        if triage_result["is_high_stakes"]:
            console.print("[bold red][HALT][/bold red] Automatic auto-merge suspended! Forced state transition to Human review.")
        else:
            console.print("[bold green][PROCEED][/bold green] Automatic auto-merge allowed to proceed.")

    # 3. Git Hooks Info
    console.print(Panel(
        "[bold green]Git Pre-Commit Hook Integration[/bold green]\n"
        "We have installed a pre-commit hook at [cyan].git/hooks/pre-commit[/cyan].\n"
        "When a developer attempts to run `git commit`, the hook queries staged changes, "
        "runs this triage logic, and rejects commits containing high-stakes modifications. "
        "This enforces corporate governance boundaries locally before push events occur.",
        border_style="green",
        expand=False
    ))

if __name__ == "__main__":
    main()
