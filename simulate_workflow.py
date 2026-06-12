import os
import sys
import subprocess
import shutil

# Ensure the root path is in python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.governance import parse_codeowners, triage_pr, verify_schema_compliance, verify_openapi_compliance, TelemetryScanner

def run_git_status():
    subprocess.run(["git", "status"], text=True)

def main():
    print("=" * 80)
    print("          ENTERPRISE ADVERSARIAL SWARM PR & HOOK WORKFLOW SIMULATOR          ")
    print("=" * 80)

    # Load CODEOWNERS rules
    codeowners_path = "mock_infrastructure/CODEOWNERS"
    with open(codeowners_path, "r", encoding="utf-8") as f:
        codeowners_content = f.read()
    rules = parse_codeowners(codeowners_content)

    # ------------------------------------------------------------------------
    # STEP 1: Simulate Low-Stakes PR Workflow (Frontend/Cart tier)
    # ------------------------------------------------------------------------
    print("\n--- [STEP 1] Simulating Low-Stakes PR (Frontend/Cart Service) ---")
    low_stakes_files = ["src/cart/cart_service.py"]
    print(f"Developer modifies files: {low_stakes_files}")
    
    triage_1 = triage_pr(low_stakes_files, rules)
    print(f"Compliance Triage Status: {triage_1['status']}")
    print(f"Is High-Stakes?         : {triage_1['is_high_stakes']}")
    print(f"Required Owner Pools    : {triage_1['required_approvals']}")
    print("[RESULT] Triage APPROVED. Codeband automatically proceeds with review & merge.")

    # ------------------------------------------------------------------------
    # STEP 2: Simulate High-Stakes PR Compliance Interception (Auth tier)
    # ------------------------------------------------------------------------
    print("\n--- [STEP 2] Simulating High-Stakes PR Interception (Security/Auth Service) ---")
    high_stakes_files = ["src/auth/auth_service.py"]
    print(f"Developer modifies files: {high_stakes_files}")
    
    triage_2 = triage_pr(high_stakes_files, rules)
    print(f"Compliance Triage Status: {triage_2['status']}")
    print(f"Is High-Stakes?         : {triage_2['is_high_stakes']}")
    print(f"Required Owner Pools    : {triage_2['required_approvals']}")
    print("\n[INTERCEPTION DETECTED]")
    print("Auto-merge is halted. Forced state change to PENDING_HUMAN_APPROVAL.")

    # ------------------------------------------------------------------------
    # STEP 3: Simulate Bounded Context Review (Adversarial Schema Violation)
    # ------------------------------------------------------------------------
    print("\n--- [STEP 3] Simulating Bounded Context Mismatch (Adversarial Model Check) ---")
    print("Claude Coder submits code containing a database schema violation:")
    violating_code = """
    def add_discount(cart_id, coupon):
        # Mismatch: discount_applied column does not exist in public.cart_items
        db.execute("INSERT INTO cart_items (cart_id, product_id, discount_applied) VALUES (1, 2, 0.15)")
    """
    print("-" * 50)
    print(violating_code.strip())
    print("-" * 50)
    
    print("Codex Cart/Auth SME runs MCP-based compliance verification...")
    schema_check = verify_schema_compliance(violating_code, "mock_infrastructure/postgres_schema.sql")
    print(f"MCP Schema Compliant: {schema_check['compliant']}")
    print(f"MCP Schema Violations: {schema_check['violations']}")
    print("[RESULT] Review FAILED. Mismatch detected, blocking invalid schema deployment.")

    # ------------------------------------------------------------------------
    # STEP 4: Simulate Bounded Context Review (Adversarial OpenAPI Contract Violation)
    # ------------------------------------------------------------------------
    print("\n--- [STEP 4] Simulating OpenAPI Contract Mismatch (Adversarial Model Check) ---")
    print("Claude Coder submits code lacking the required 'cart_id' parameter:")
    violating_openapi_code = """
    def perform_checkout(payload):
        # Mismatch: missing the required unique identifier property for OpenAPI
        payment_token = payload["payment_method_token"]
        return api_post("/api/v1/checkout", data={"payment_method_token": payment_token})
    """
    print("-" * 50)
    print(violating_openapi_code.strip())
    print("-" * 50)
    
    print("Codex Cart/Auth SME runs OpenAPI schema compliance verification...")
    openapi_check = verify_openapi_compliance(violating_openapi_code, "mock_infrastructure/openapi_contract.json")
    print(f"MCP OpenAPI Compliant: {openapi_check['compliant']}")
    print(f"MCP OpenAPI Violations: {openapi_check['violations']}")
    print("[RESULT] Review FAILED. Missing contract parameters flagged.")

    # ------------------------------------------------------------------------
    # STEP 5: Simulate Observability watchdog log streaming checks
    # ------------------------------------------------------------------------
    print("\n--- [STEP 5] Simulating Observability watchdog logs stream checks ---")
    print("ObservabilityAgent scans mock log stream mock_infrastructure/app_logs.json...")
    scanner = TelemetryScanner("mock_infrastructure/app_logs.json")
    anomalies = scanner.scan_leaks()
    print(f"Anomalies detected: {len(anomalies)}")
    for anomaly in anomalies:
        print(f"  [{anomaly['level']}] [{anomaly['service']}] {anomaly['message']}")

    print("=" * 80)
    print("                      ALL WORKFLOW SIMULATIONS COMPLETED                     ")
    print("=" * 80)

if __name__ == "__main__":
    main()
