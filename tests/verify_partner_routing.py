import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

def test_partner_endpoint_routing():
    print("=" * 60)
    print("RUNNING PARTNER ENDPOINT ROUTING DIAGNOSTIC")
    print("=" * 60)

    # Load environment variables
    load_dotenv()

    # 1. Inspect environment state
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    print(f"[INFO] Target Base URL: {base_url}")
    if not api_key:
        print("[FAIL] OPENAI_API_KEY is missing from the environment.")
        sys.exit(1)
    if not base_url or "aimlapi" not in base_url:
        print("[FAIL] OPENAI_BASE_URL is not set to the AI/ML API endpoint.")
        sys.exit(1)

    # 2. Initialize Client mirroring Codeband's initialization pattern
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        print("[INFO] OpenAI Client initialized with custom base_url configuration.")
        
        # Verify internal client configuration properties
        print(f"[INFO] Verified Client API Base: {client.base_url}")
        
        # 3. Force a lightweight chat completion handshake using a cheap model
        print("[INFO] Attempting handshake request to partner model repository...")
        response = client.chat.completions.create(
            model="gpt-4o-mini", # AI/ML API maps standard names to their serverless catalog
            messages=[{"role": "user", "content": "Ping"}],
            max_tokens=5
        )
        
        content = response.choices[0].message.content.strip()
        print(f"[INFO] Handshake Response: '{content}'")
        print("[SUCCESS] Traffic successfully routed to AI/ML API partner platform!")
        print("=" * 60)
        
    except Exception as e:
        print(f"[FAIL] Connection handshake failed.")
        print(f"[ERROR DETAILS]: {str(e)}")
        print("\n[REMEDY] Double check that your AI/ML API key is pasted correctly into the OPENAI_API_KEY slot.")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    test_partner_endpoint_routing()
