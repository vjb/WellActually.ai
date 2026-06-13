import os
import asyncio
from dotenv import load_dotenv
from thenvoi_rest import AsyncRestClient

load_dotenv("c:\\Users\\vjbel\\hacks\\BOA\\.env")
api_key = os.getenv("BAND_API_KEY")

async def inspect():
    client = AsyncRestClient(api_key=api_key, base_url="https://app.band.ai")
    for service_name in dir(client):
        if service_name.startswith("human_") or service_name.startswith("agent_"):
            service = getattr(client, service_name)
            print(f"{service_name}:")
            for attr in dir(service):
                if not attr.startswith("_"):
                    print(f"  {attr}")

if __name__ == "__main__":
    asyncio.run(inspect())
