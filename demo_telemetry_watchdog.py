import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure root path is in python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.governance import TelemetryScanner

console = Console()

def main():
    console.print(Panel(
        "[bold cyan]COMPONENT DEMO: CONTEXT-AWARE TELEMETRY WATCHDOG[/bold cyan]\n"
        "[dim]Demonstrating Observability Log Scanning for Memory Leaks and DB Pool Exhaustion[/dim]",
        border_style="cyan",
        expand=False
    ))

    log_path = "mock_infrastructure/app_logs.json"
    if not os.path.exists(log_path):
        console.print(f"[bold red]Error:[/bold red] Log file not found at {log_path}")
        return

    # 1. Initialize TelemetryScanner
    scanner = TelemetryScanner(log_path)
    
    console.print(f"\n[bold magenta]Scanning Log Stream: {log_path}...[/bold magenta]")
    
    # 2. Scan for anomalies
    anomalies = scanner.scan_leaks()
    
    console.print(f"\nFound [bold yellow]{len(anomalies)}[/bold yellow] critical anomalies in the log stream:")

    # 3. Format and print anomalies in a Table
    table = Table(title="Watchdog Log Anomalies detected", show_header=True, header_style="bold magenta")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Service", style="green")
    table.add_column("Level", style="bold red")
    table.add_column("Message", style="white")

    for anomaly in anomalies:
        table.add_row(
            anomaly.get("timestamp"),
            anomaly.get("service"),
            anomaly.get("level"),
            anomaly.get("message")
        )
    console.print(table)

    # 4. Show Watchdog Alert Broadcast Panels
    console.print("\n[bold red]Simulating Watchdog Alerts Broadcast to Swarm Room Chat Feed:[/bold red]")
    for anomaly in anomalies:
        alert_text = (
            f"[bold red][ALERT] [Telemetry Watchdog] Anomaly detected in {anomaly.get('service')}![/bold red]\n"
            f"Message  : {anomaly.get('message')}\n"
            f"Timestamp: {anomaly.get('timestamp')}"
        )
        console.print(Panel(alert_text, border_style="bold red", expand=False))

if __name__ == "__main__":
    main()
