import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv()

def main():
    repo = "vjb/WellActually.ai"
    pr_number = "1"
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    gh_token = os.getenv("GH_TOKEN")
    
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Test-Client"
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            comments = json.loads(response.read().decode("utf-8"))
            if comments:
                last_comment = comments[-1]
                print(f"--- Full Body of Last Comment at {last_comment['created_at']} ---")
                print(last_comment['body'])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
