import sys
import subprocess
import os

# Ensure the project root is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.governance import parse_codeowners, triage_pr

def get_staged_files() -> list[str]:
    """
    Retrieves the list of staged files from the Git index.
    """
    try:
        output = subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True)
        return [line.strip() for line in output.splitlines() if line.strip()]
    except Exception as e:
        print(f"[ERROR] Failed to query staged files: {e}")
        return []

def main():
    print("=" * 60)
    print("[ZERO-TRUST COMPLIANCE CHECK] Running Pre-Commit Hook...")
    print("=" * 60)
    
    staged_files = get_staged_files()
    if not staged_files:
        print("[INFO] No staged files to check. Proceeding.")
        sys.exit(0)
        
    codeowners_path = "mock_infrastructure/CODEOWNERS"
    if not os.path.exists(codeowners_path):
        print(f"[WARNING] CODEOWNERS file not found at {codeowners_path}. Skipping checks.")
        sys.exit(0)
        
    with open(codeowners_path, "r", encoding="utf-8") as f:
        codeowners_content = f.read()
        
    rules = parse_codeowners(codeowners_content)
    result = triage_pr(staged_files, rules)
    
    if result["is_high_stakes"]:
        print("\n" + "!" * 60)
        print(" [ZERO-TRUST COMPLIANCE INTERCEPTION] ")
        print("!" * 60)
        print(f"Transaction Status   : {result['status']}")
        print(f"Triggered Rule paths : {staged_files}")
        print(f"Required Approvals   : {', '.join(result['required_approvals'])}")
        print("\nReason: Modifying high-stakes directories requires human sign-off.")
        print("Action: Auto-merge is HALTED. Forced state: PENDING_HUMAN_APPROVAL.")
        print("!" * 60 + "\n")
        # Exit code 1 blocks the Git commit
        sys.exit(1)
        
    print("[SUCCESS] Zero-Trust compliance check passed. Proceeding with commit.")
    print("=" * 60)
    sys.exit(0)

if __name__ == "__main__":
    main()
