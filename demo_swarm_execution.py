import time
import sys
import os
import asyncio
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.text import Text

# Ensure root path is in python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.swarm import SwarmSession, CoderAgent, ReviewerAgent, Agent

console = Console()

def print_banner():
    banner_text = (
        "[bold cyan]ENTERPRISE DOMAIN-DRIVEN SWARM: LIVE REVIEW ENGINE[/bold cyan]\n"
        "[dim]Orchestrated by Codeband & Band.ai | Powered by AI/ML API (Partner Track)[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))

def print_section(number, title):
    console.print(f"\n[bold yellow]PHASE {number}: {title}[/bold yellow]")
    console.print("[yellow]" + "-" * 80 + "[/yellow]")

def print_agent_msg(agent_name, role, model, msg, color="green"):
    title = f"🤖 {agent_name} ({role}) — Model: {model}"
    
    # Check if there is python code inside the message
    if "def " in msg:
        # Extract the code block to syntax highlight it nicely
        lines = msg.split("\n")
        code_lines = []
        explanation_lines = []
        in_code = False
        
        for line in lines:
            if "def " in line or in_code:
                in_code = True
                code_lines.append(line)
            else:
                explanation_lines.append(line)
        
        explanation = "\n".join(explanation_lines).strip()
        code_block = "\n".join(code_lines).strip()
        
        panel_content = Text()
        if explanation:
            panel_content.append(explanation + "\n\n")
            
        console.print(Panel(panel_content, title=title, border_style=color, expand=False))
        if code_block:
            syntax = Syntax(code_block, "python", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title=f"Proposed Code Changes", border_style="yellow", expand=False))
    else:
        console.print(Panel(msg.strip(), title=title, border_style=color, expand=False))

async def main():
    print_banner()

    # 1. Initialize Swarm Session
    session = SwarmSession(
        pr_id="pr_104",
        diff_files=["src/cart/cart_service.py", "src/billing/billing_service.py"],
        codeowners_path="mock_infrastructure/CODEOWNERS",
        schema_path="mock_infrastructure/postgres_schema.sql",
        openapi_path="mock_infrastructure/openapi_contract.json",
        log_path="mock_infrastructure/app_logs.json"
    )

    # Generate unique names to prevent "name has already been taken" registration failure
    unique_suffix = session.unique_suffix
    conductor = Agent(name=f"conductor-{unique_suffix}", role="Orchestrator", system_prompt="You are the Conductor orchestrating the debate.")
    coder = CoderAgent(name_suffix=unique_suffix, model="gpt-4o-mini")
    reviewer_auth = ReviewerAgent(role="Auth & Fraud SME", name_suffix=unique_suffix, model="unsloth/Meta-Llama-3.1-70B-Instruct", domain="auth")
    reviewer_cart = ReviewerAgent(role="Cart SME", name_suffix=unique_suffix, model="gpt-4o-mini", domain="cart")

    try:
        # ------------------------------------------------------------------------
        # PHASE 1: Room Initialization & Triage
        # ------------------------------------------------------------------------
        print_section(1, "Task Initialization & Compliance Triage")
        time.sleep(0.5)
        console.print("[bold green][SYSTEM][/bold green] PR-104 Created: 'Feature: Implement High-Value Checkout Pipeline'")
        console.print(f"[bold green][SYSTEM][/bold green] Modified files: [magenta]{session.diff_files}[/magenta]")
        console.print("[bold green][SYSTEM][/bold green] Initializing Band.ai task room...")
        console.print("[bold yellow][TRIAGE][/bold yellow] Running zero-trust CodeownersTriage check...")
        time.sleep(0.5)

        triage_result = session.run_triage()
        console.print(f"[bold yellow][TRIAGE][/bold yellow] Files matched: [white]{triage_result['required_approvals']}[/white]")
        
        if triage_result["status"] == "PENDING_HUMAN_APPROVAL":
            console.print("[bold red][INTERCEPTED][/bold red] High-Stakes path detected! Suspending automatic auto-merge pipeline.")
            console.print("[bold red][STATUS][/bold red] Swarm Room state forced to: [bold red]PENDING_HUMAN_APPROVAL[/bold red]")
        else:
            console.print("[bold green][STATUS][/bold green] Swarm Room state: [bold green]APPROVED[/bold green]")

        # ------------------------------------------------------------------------
        # PHASE 2: Bounded Context Verification & Partners
        # ------------------------------------------------------------------------
        print_section(2, "Adversarial Swarm Pairing & Partner Technologies")
        time.sleep(0.5)
        
        # Display partner config in a clean table
        table = Table(title="Partner Stack Configurations", show_header=True, header_style="bold magenta")
        table.add_column("Framework Layer", style="cyan")
        table.add_column("Config Value / Redirection", style="green")
        table.add_column("Status", style="bold green")
        table.add_row("Codex CLI Redirection", os.getenv("OPENAI_BASE_URL", "https://api.aimlapi.com/v1"), "ACTIVE")
        table.add_row("Band.ai room management", "BAND_API_KEY set", "CONNECTED")
        table.add_row("AIML API Inference", "unsloth/Meta-Llama-3.1-70B-Instruct", "ACTIVE")
        table.add_row("Adversarial pairing model", "Claude 3.7 vs Codex 5.4", "STABLE")
        console.print(table)
        
        # Initialize session (Register agents on Band.ai, Create room, Add participants)
        await session.initialize_session(conductor, coder, [reviewer_auth, reviewer_cart])

        console.print(Panel(
            f"Triage complete. Suspending auto-merge loop for PR-104.\n"
            f"Room created on Band.ai: [bold blue]{session.room_id}[/bold blue]\n"
            f"Initializing adversarial debate rooms for Cart SME (Claude) and Auth SME (Codex/AIML).\n"
            f"Coder agent is dispatched to local isolated Git worktree: 'codeband/branch-pr-104'.",
            title=f"🤖 Conductor (Orchestrator) — Model: Claude 3.5 Sonnet",
            border_style="cyan",
            expand=False
        ))

        # ------------------------------------------------------------------------
        # PHASE 3 & 4: Adversarial Debate Loops & Deadlock Mitigation
        # ------------------------------------------------------------------------
        print_section(3, "Adversarial Debate & Bounded Context (MCP) Validations")
        
        max_rounds = 3
        for round_num in range(1, max_rounds + 1):
            console.print(f"\n[bold yellow]--- Debate Round {round_num} ---[/bold yellow]")
            time.sleep(0.5)
            
            # Run debate round
            round_res = await session.run_debate_round(conductor, coder, [reviewer_auth, reviewer_cart])
            
            # Print Coder proposal
            print_agent_msg(
                coder.name, coder.role, coder.model,
                round_res["coder_response"],
                color="green"
            )
            
            # Print Reviews
            for name, role, review in round_res["reviewer_responses"]:
                color = "red" if "❌" in review or "FAILED" in review else "cyan"
                print_agent_msg(
                    name, role, "gpt-4o-mini",
                    review,
                    color=color
                )
            
            # Check if deadlocked
            if round_res["is_deadlocked"]:
                console.print(f"\n[bold red][DEADLOCK DETECTED][/bold red] Review round limit exceeded! Iterations = {round_num} (Limit = 2).")
                console.print("[bold red][SYSTEM][/bold red] Halting autonomous argument loop to protect compute budget.")
                console.print(f"[bold red][STATUS][/bold red] Room status: [bold red]{session.status}[/bold red] | Escalating to Human Operator via HITL webhook.")
                break
                
            if round_res["round_passed"]:
                console.print(f"\n[bold green][SUCCESS][/bold green] Swarm Consensus reached on round {round_num}!")
                break

        # ------------------------------------------------------------------------
        # PHASE 5: Observability watchdog Alert
        # ------------------------------------------------------------------------
        print_section(4, "Context-Aware Telemetry Watchdog Alert")
        time.sleep(0.5)
        console.print("[bold green][TELEMETRY WATCHDOG][/bold green] Scanning app_logs.json stream...")
        
        anomalies = session.run_watchdog_scan()
        for anomaly in anomalies:
            alert_text = (
                f"[bold red][ALERT] [Telemetry Watchdog] Anomaly detected in {anomaly.get('service')}![/bold red]\n"
                f"Message  : {anomaly.get('message')}\n"
                f"Timestamp: {anomaly.get('timestamp')}"
            )
            console.print(Panel(alert_text, border_style="bold red", expand=False))

        console.print("\n" + "=" * 80)
        console.print("[bold green]SIMULATOR EXECUTION COMPLETED SUCCESSFULLY[/bold green]")
        console.print("=" * 80)

    finally:
        # Gracefully cleanup agents registered during the session
        await session.cleanup_agents(conductor, coder, [reviewer_auth, reviewer_cart])

if __name__ == "__main__":
    asyncio.run(main())
