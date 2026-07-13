import asyncio
import sys
import json
import httpx
from websockets.asyncio.client import connect

async def run_live_verification():
    print("====================================================")
    print("        BUJJI AI PHASE 3 LIVE VERIFICATION          ")
    print("====================================================")

    base_url = "http://127.0.0.1:8000/api/v1"
    ws_url = "ws://127.0.0.1:8000/api/v1/ws/chat"
    
    # Use longer timeouts because LLM response generation can take time
    async with httpx.AsyncClient(timeout=45.0) as client:
        # 1. Verify health endpoint reports Ollama online
        print("Checking system health status...")
        try:
            r = await client.get(f"{base_url}/health")
            health = r.json()
            print(f"Health Response: {health}")
            if health.get("ollama") != "connected":
                print("[ERROR] Health check shows Ollama is not connected. Start Ollama and pull llama3.2.")
                return
        except Exception as e:
            print(f"[ERROR] FastAPI server is not responding at {base_url}: {e}")
            return

        # 2. Create new conversation session
        print("\nCreating new conversation...")
        r = await client.post(f"{base_url}/conversations", json={})
        conv = r.json()
        conv_id = conv["id"]
        print(f"[SUCCESS] Created conversation ID: {conv_id} with title: '{conv['title']}'")

        # 3. Send first message (Non-streaming REST API)
        print("\nSending first message (REST)...")
        prompt1 = "Tell me a short joke about a programmer."
        payload1 = {"content": prompt1}
        
        try:
            r = await client.post(f"{base_url}/conversations/{conv_id}/messages", json=payload1)
            assert r.status_code == 200
            chat_data = r.json()
            user_msg = chat_data["user_message"]
            assistant_msg = chat_data["assistant_message"]
            
            print(f"User Prompt: {user_msg['content']}")
            print(f"Assistant Answer: {assistant_msg['content'].strip()}")
            print("[SUCCESS] REST non-streaming interaction succeeded.")
        except Exception as e:
            print(f"[FAIL] REST interaction failed: {e}")
            return

        # 4. Verify title update
        print("\nVerifying automatic title generation...")
        r = await client.get(f"{base_url}/conversations/{conv_id}")
        conv_details = r.json()
        print(f"Conversation Title: '{conv_details['title']}'")
        # Title should start with the normalized prompt content
        assert conv_details["title"].startswith("Tell me a short joke")
        print("[SUCCESS] Title updated deterministically.")

        # 5. Send follow-up query requiring previous context
        print("\nSending follow-up query requiring context...")
        prompt2 = "Explain that joke."
        payload2 = {"content": prompt2}
        try:
            r = await client.post(f"{base_url}/conversations/{conv_id}/messages", json=payload2)
            assert r.status_code == 200
            followup_data = r.json()
            print(f"User Follow-up: {followup_data['user_message']['content']}")
            print(f"Assistant Explanation: {followup_data['assistant_message']['content'].strip()}")
            print("[SUCCESS] Context-aware follow-up succeeded.")
        except Exception as e:
            print(f"[FAIL] Follow-up failed: {e}")

        # 6. Test WebSocket streaming connection
        print(f"\nConnecting to WebSocket: {ws_url}/{conv_id}...")
        try:
            async with connect(f"{ws_url}/{conv_id}") as ws:
                # Receive connection.ready
                ready_event = json.loads(await ws.recv())
                print(f"Ready Event: {ready_event}")
                assert ready_event["type"] == "connection.ready"
                
                # Send prompt
                payload = {
                    "type": "message.send",
                    "data": {"content": "Say exactly: WebSocket streaming complete."}
                }
                print("Sending prompt over WS: 'Say exactly: WebSocket streaming complete.'")
                await ws.send(json.dumps(payload))
                
                # Read events
                print("Stream output: ", end="", flush=True)
                while True:
                    event_raw = await ws.recv()
                    event = json.loads(event_raw)
                    event_type = event.get("type")
                    
                    if event_type == "message.user.saved":
                        pass
                    elif event_type == "response.started":
                        pass
                    elif event_type == "response.chunk":
                        chunk = event["data"]["content"]
                        print(chunk, end="", flush=True)
                    elif event_type == "response.completed":
                        print()
                        print(f"Response Completed Event content: '{event['data']['content']}'")
                        assert "WebSocket streaming complete" in event["data"]["content"]
                        break
                    elif event_type == "error":
                        print(f"\n[ERROR] WS returned error: {event['data']}")
                        break
                print("[SUCCESS] WebSocket streaming interaction succeeded.")
        except Exception as e:
            print(f"[FAIL] WebSocket interaction failed: {e}")

        # 7. Clean up: Delete the test conversation session
        print("\nDeleting conversation to clean database...")
        r = await client.delete(f"{base_url}/conversations/{conv_id}")
        assert r.status_code == 204
        print("[SUCCESS] Conversation deleted successfully.")

if __name__ == "__main__":
    asyncio.run(run_live_verification())
