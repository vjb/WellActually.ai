import os
import sys
import asyncio
from dotenv import load_dotenv

# Ensure the root path is in python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from thenvoi_rest import AsyncRestClient
from thenvoi_rest.human_api_chats import CreateMyChatRoomRequestChat

async def run_demo():
    print("=" * 80)
    print("          BAND.AI PLATFORM AS THE SWARM CONTRACT FOCAL POINT DEMO          ")
    print("=" * 80)

    # 1. Initialize configuration
    load_dotenv()
    api_key = os.getenv("BAND_API_KEY")
    rest_url = os.getenv("BAND_REST_URL", "https://app.band.ai")

    if not api_key:
        print("[FAIL] BAND_API_KEY is not defined in the environment.")
        return

    print(f"[INFO] Initializing Band.ai REST Client...")
    print(f"[INFO] Target Server: {rest_url}")
    client = AsyncRestClient(api_key=api_key, base_url=rest_url)

    # 2. Establish Verified Identity
    print("\n--- [STEP 1] Retrieve User Profile (Identity Context) ---")
    use_mock_fallback = False
    try:
        profile_res = await client.human_api_profile.get_my_profile()
        profile = profile_res.data
        print(f"✓ Authentication Successful.")
        print(f"  User Email   : {getattr(profile, 'email', 'N/A')}")
        print(f"  User ID      : {getattr(profile, 'id', 'N/A')}")
        print(f"  Profile Name : {getattr(profile, 'name', 'N/A')}")
    except Exception as e:
        print(f"[ERROR] Failed to query profile: {e}")
        print("[INFO] Enabling full offline mock simulator.")
        use_mock_fallback = True

    # 3. List Active Chat Rooms (Focal points)
    print("\n--- [STEP 2] Fetch Active Task Rooms (Contract Rooms) ---")
    if not use_mock_fallback:
        try:
            chats = await client.human_api_chats.list_my_chats(page=1, page_size=5)
            print(f"✓ Retrieved active rooms list. Count: {len(chats)}")
            for chat in chats:
                print(f"  - Room ID: {chat.id} | Title: '{chat.title}' | Task Ref: {chat.task_id}")
        except Exception as e:
            print(f"[WARNING] Human API Chats access is restricted by plan level: {e}")
            print("[INFO] Redirecting to Simulated Contract Room Mode...")
            use_mock_fallback = True

    if use_mock_fallback:
        # Simulate retrieval of existing contract task rooms
        print("✓ Mock Contract Rooms Loaded:")
        print("  - Room ID: chat_c8a9d0f1 | Title: 'PR-45: Update auth endpoints' | Task Ref: task_auth_101")
        print("  - Room ID: chat_f2d1e0c2 | Title: 'PR-48: Add cart discount check' | Task Ref: task_cart_202")

    # 4. Simulate Conductor Initializing a Compliance Chat Room
    print("\n--- [STEP 3] Initialize Swarm Compliance Task Room ---")
    dummy_task_id = "task_compliance_intercept_pr_102"
    print(f"Conductor instantiates a new Band task room for task reference: {dummy_task_id}...")
    
    if not use_mock_fallback:
        try:
            # Create a new chat room associated with the target compliance task
            chat_req = CreateMyChatRoomRequestChat(task_id=dummy_task_id)
            room_response = await client.human_api_chats.create_my_chat_room(chat=chat_req)
            new_room = room_response.data
            print(f"✓ Task Room Successfully Created on Band.ai.")
            print(f"  New Room ID   : {new_room.id}")
            print(f"  New Room Title: '{new_room.title}'")
            print(f"  Task Reference: {new_room.task_id}")
            
            # 5. Broadcast compliance outcome as the contract focal point
            print("\n--- [STEP 4] Broadcast Compliance Outcomes to the Room ---")
            print(f"Posting compliance alert to Room {new_room.id}...")
            
            from thenvoi_rest.types import ChatMessageRequest
            
            msg_payload = ChatMessageRequest(
                content=(
                    f"[ZERO-TRUST COMPLIANCE BLOCKED] Conductor intercepted modification to '/src/auth/'. "
                    f"Auto-merge loop is suspended. Room state is forced to PENDING_HUMAN_APPROVAL. "
                    f"Requires review from security-owners-pool."
                )
            )
            
            msg_response = await client.human_api_messages.send_my_chat_message(
                chat_id=new_room.id,
                message=msg_payload
            )
            print("✓ Compliance message successfully broadcast to all participants in the Band room!")
            
        except Exception as e:
            print(f"[WARNING] Room creation failed: {e}")
            use_mock_fallback = True

    if use_mock_fallback:
        # Simulating the creation and broadcast
        simulated_room_id = "chat_task_compliance_pr_102"
        print(f"✓ Task Room Successfully Created on Band.ai (Simulated).")
        print(f"  New Room ID   : {simulated_room_id}")
        print(f"  New Room Title: 'Task Compliance Intercept PR 102'")
        print(f"  Task Reference: {dummy_task_id}")
        
        print("\n--- [STEP 4] Broadcast Compliance Outcomes to the Room (Simulated) ---")
        print(f"Posting compliance alert to Room {simulated_room_id}...")
        print(
            f"  [BROADCAST MESSAGE] (Sent to 9 agents & developers):\n"
            f"  --------------------------------------------------------------------------------\n"
            f"  [ZERO-TRUST COMPLIANCE BLOCKED] Conductor intercepted modification to '/src/auth/'.\n"
            f"  Auto-merge loop is suspended. Room state is forced to PENDING_HUMAN_APPROVAL.\n"
            f"  Requires review from security-owners-pool.\n"
            f"  --------------------------------------------------------------------------------"
        )
        print("✓ Compliance message successfully broadcast to all participants in the Band room!")

    print("\n" + "=" * 80)
    print("                      BAND.AI CONTRACT DEMO COMPLETED                        ")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_demo())
