import os
import sys
import shutil
import subprocess
import time
import urllib.request
import urllib.error
import json
from dotenv import load_dotenv

def log(msg):
    print(f"[DEMO PR CREATOR] {msg}", flush=True)

def remove_readonly(func, path, excinfo):
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)

def cleanup_temp_dir(path):
    if os.path.exists(path):
        log(f"Cleaning up directory: {path}")
        try:
            shutil.rmtree(path, onerror=remove_readonly)
        except Exception:
            # Fallback to shell rmdir under Windows
            subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    load_dotenv()
    
    gh_token = os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPO", "vjb/WellActually.ai")
    
    if not gh_token or gh_token.startswith("ghp_mock") or "pat" not in gh_token.lower():
        log("ERROR: A valid GH_TOKEN must be configured in your .env file to create a real Pull Request.")
        sys.exit(1)
        
    log(f"Configured repository: {repo}")
    
    # Path for temp clone
    temp_dir = os.path.abspath(os.path.join("scratch", "temp_clone"))
    cleanup_temp_dir(temp_dir)
    os.makedirs(os.path.dirname(temp_dir), exist_ok=True)
    
    # Clone url with token for auth
    clone_url = f"https://{gh_token}@github.com/{repo}.git"
    log("Cloning repository from GitHub...")
    
    try:
        subprocess.run(
            ["git", "-c", "credential.helper=", "clone", clone_url, temp_dir],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        log(f"ERROR: Failed to clone repository: {e.stderr.decode('utf-8')}")
        sys.exit(1)
        
    # Generate branch name
    timestamp = int(time.time())
    branch_name = f"demo/pr-{timestamp}"
    log(f"Creating branch: {branch_name}")
    
    try:
        # Configure git user details inside the temp clone
        subprocess.run(["git", "config", "user.name", "Demo Bot"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "bot@wellactually.ai"], cwd=temp_dir, check=True)
        
        # Checkout new branch
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=temp_dir, check=True)
        
        # Create src/billing
        billing_dir = os.path.join(temp_dir, "src", "billing")
        os.makedirs(billing_dir, exist_ok=True)
        
        # Write spending_report.py
        report_file = os.path.join(billing_dir, "spending_report.py")
        code_content = """# Spending Report Fetcher Endpoint (Demo)
import db

def get_spending(user_id):
    # Retrieve user's spending limit and discount tier from postgres
    # WARNING: Column 'discount_tier' does not exist in 'billing_profiles' schema.
    # WARNING: Direct access to 'billing_profiles.spending_limit_usd' without RBAC role verification.
    return db.query("SELECT spending_limit_usd, discount_tier FROM billing_profiles WHERE user_id = %s", user_id)
"""
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(code_content)
            
        log("Wrote src/billing/spending_report.py")
        
        # Commit changes
        subprocess.run(["git", "add", "src/billing/spending_report.py"], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "feat: implement spending report fetcher endpoint"], cwd=temp_dir, check=True)
        
        # Push branch
        log(f"Pushing branch {branch_name} to GitHub...")
        push_success = False
        
        # Try pushing with token first
        token_push_url = f"https://{gh_token}@github.com/{repo}.git"
        log("Attempting push using GH_TOKEN in URL...")
        try:
            subprocess.run(
                ["git", "-c", "credential.helper=", "push", token_push_url, branch_name],
                cwd=temp_dir,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            push_success = True
            log("✓ Branch pushed successfully using GH_TOKEN.")
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode("utf-8")
            log(f"Push with GH_TOKEN failed: {err_msg.strip()}")
            log("Attempting fallback push using parent repository's configured origin URL...")
            
            # Get parent origin URL
            parent_origin = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True
            ).stdout.strip()
            
            if parent_origin:
                log(f"Parent origin URL detected: {parent_origin}")
                try:
                    subprocess.run(
                        ["git", "push", parent_origin, branch_name],
                        cwd=temp_dir,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE
                    )
                    push_success = True
                    log("✓ Branch pushed successfully using system git credentials.")
                except subprocess.CalledProcessError as e2:
                    log(f"ERROR: Fallback push also failed: {e2.stderr.decode('utf-8').strip()}")
            else:
                log("ERROR: Could not retrieve parent origin URL.")
                
        if not push_success:
            raise subprocess.CalledProcessError(1, "git push")
        
    except subprocess.CalledProcessError as e:
        log("ERROR: Git operation failed.")
        cleanup_temp_dir(temp_dir)
        sys.exit(1)
        
    # Create Pull Request
    log("Creating Pull Request on GitHub...")
    pr_url = f"https://api.github.com/repos/{repo}/pulls"
    payload = {
        "title": "Implement spending report fetcher endpoint",
        "head": branch_name,
        "base": "main",
        "body": "This PR implements a new endpoint to retrieve a user's spending limit and discount tier. It queries the `billing_profiles` table for `spending_limit_usd` and `discount_tier`."
    }
    
    req = urllib.request.Request(
        pr_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"token {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "WellActually-Demo-Bot"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            pr_num = res_data.get("number")
            pr_html_url = res_data.get("html_url")
            log(f"SUCCESS: Created Pull Request #{pr_num}")
            log(f"PR URL: {pr_html_url}")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        log(f"ERROR: GitHub API responded with HTTP {e.code}: {err_msg}")
    except Exception as e:
        log(f"ERROR: Failed to create Pull Request: {e}")
        
    # Cleanup temp clone
    cleanup_temp_dir(temp_dir)
    log("Done!")

if __name__ == "__main__":
    main()
