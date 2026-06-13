import os
import asyncio
from dotenv import load_dotenv
from thenvoi_rest import AsyncRestClient

load_dotenv("c:\\Users\\vjbel\\hacks\\BOA\\.env")
api_key = os.getenv("BAND_REUSE_CONDUCTOR_KEY")

async def inspect():
    client = AsyncRestClient(api_key=api_key, base_url="https://app.band.ai")
    
    # List agent chats
    chats_resp = await client.agent_api_chats.list_agent_chats()
    chats = chats_resp.data
    print(f"Found {len(chats)} agent chats.")
    if chats:
        print("First agent chat:")
        print(chats[0])

if __name__ == "__main__":
    asyncio.run(inspect())
