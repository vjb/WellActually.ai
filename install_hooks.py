import os
import stat
import sys

def install_hook():
    git_dir = ".git"
    if not os.path.isdir(git_dir):
        print("[ERROR] .git directory not found. Are you in the repository root?")
        sys.exit(1)
        
    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    
    pre_commit_path = os.path.join(hooks_dir, "pre-commit")
    
    # Write pre-commit hook file
    # Shell script invocation of python script (portable across Unix and Git Bash on Windows)
    hook_content = (
        "#!/bin/sh\n"
        '".venv/Scripts/python" src/githooks/compliance_hook.py\n'
    )
    
    with open(pre_commit_path, "w", newline="\n") as f:
        f.write(hook_content)
        
    # Make executable
    try:
        st = os.stat(pre_commit_path)
        os.chmod(pre_commit_path, st.st_mode | stat.S_IEXEC)
    except Exception as e:
        print(f"[WARNING] Failed to set execute permissions on hook: {e}")
        
    print(f"[SUCCESS] Compliance git pre-commit hook installed to: {pre_commit_path}")

if __name__ == "__main__":
    install_hook()
