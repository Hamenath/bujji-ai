import asyncio
import sys
import json
import httpx
from websockets.asyncio.client import connect

async def run_live_agent_verification():
    print("====================================================")
    print("         BUJJI AI PHASE 4 LIVE AGENT VERIFICATION   ")
    print("====================================================")

    base_url = "http://127.0.0.1:8000/api/v1"
    ws_url = "ws://127.0.0.1:8000/api/v1/ws/chat"
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        # 1. Verify health
        print("Checking health...")
        try:
            r = await client.get(f"{base_url}/health")
            health = r.json()
            if health.get("ollama") != "connected":
                print("[ERROR] Ollama is not connected. Start Ollama and run verification.")
                return
            print("[SUCCESS] Ollama is ONLINE.")
        except Exception as e:
            print(f"[ERROR] FastAPI server is not responding: {e}")
            return

        # 2. Create conversation
        print("\nCreating new conversation...")
        r = await client.post(f"{base_url}/conversations", json={})
        conv = r.json()
        conv_id = conv["id"]
        print(f"[SUCCESS] Conversation ID: {conv_id}")

        # 3. Test Direct Route (no tools needed)
        print("\n1. Testing Direct Route...")
        payload_direct = {"content": "Explain recursion in one sentence."}
        try:
            r = await client.post(f"{base_url}/conversations/{conv_id}/agent", json=payload_direct)
            assert r.status_code == 201
            res_data = r.json()
            print(f"Route: {res_data['route']}")
            print(f"Status: {res_data['status']}")
            print(f"Response: {res_data['response'].strip()}")
            assert res_data["route"] == "direct"
            assert len(res_data["steps"]) == 0
            print("[SUCCESS] Direct route verified.")
        except Exception as e:
            print(f"[FAIL] Direct route failed: {e}")
            return

        # 4. Test Tool Route (Calculator)
        print("\n2. Testing Tool Route...")
        payload_tool = {"content": "Calculate 125 * 48."}
        try:
            r = await client.post(f"{base_url}/conversations/{conv_id}/agent", json=payload_tool)
            assert r.status_code == 201
            res_data = r.json()
            print(f"Route: {res_data['route']}")
            print(f"Status: {res_data['status']}")
            print(f"Response: {res_data['response'].strip()}")
            assert res_data["route"] == "agent"
            assert len(res_data["steps"]) == 1
            assert res_data["steps"][0]["tool_name"] == "calculator"
            assert res_data["steps"][0]["success"] is True
            assert "6000" in res_data["response"]
            print("[SUCCESS] Tool route verified.")
        except Exception as e:
            print(f"[FAIL] Tool route failed: {e}")
            return

        # 5. Test WebSocket Agent Event Flow
        print(f"\n3. Testing WebSocket Agent Streaming Events at: {ws_url}/{conv_id}...")
        try:
            async with connect(f"{ws_url}/{conv_id}") as ws:
                ready_event = json.loads(await ws.recv())
                assert ready_event["type"] == "connection.ready"
                
                # Send agent.run event
                payload = {
                    "type": "agent.run",
                    "data": {"content": "Calculate 125 * 48."}
                }
                print("Sending 'Calculate 125 * 48.' over WebSocket...")
                await ws.send(json.dumps(payload))
                
                expected_events = [
                    "message.user.saved",
                    "agent.started",
                    "agent.route.selected",
                    "agent.plan.created",
                    "tool.started",
                    "tool.completed",
                    "response.chunk",
                    "agent.completed"
                ]
                
                received_events = []
                while True:
                    event_raw = await ws.recv()
                    event = json.loads(event_raw)
                    event_type = event.get("type")
                    received_events.append(event_type)
                    
                    print(f" -> Event: {event_type} - {event['data']}")
                    
                    if event_type == "agent.completed":
                        assert "6000" in event["data"]["final_response"]
                        break
                    elif event_type == "error":
                        print(f"[ERROR] WS returned: {event['data']}")
                        break
                
                # Check that crucial events were received
                for ev in ["agent.started", "agent.route.selected", "agent.plan.created", "tool.completed", "agent.completed"]:
                    assert ev in received_events
                print("[SUCCESS] WebSocket Agent events flow verified.")
        except Exception as e:
            print(f"[FAIL] WebSocket Agent flow failed: {e}")

        # 6. Verify Database records and Exactly-once assistant message persistence
        print("\n4. Verifying DB Persistence records...")
        try:
            # Get conversation history
            r = await client.get(f"{base_url}/conversations/{conv_id}")
            conv_details = r.json()
            messages = conv_details["messages"]
            
            # Count assistant messages
            assistant_messages = [m for m in messages if m["role"] == "assistant"]
            user_messages = [m for m in messages if m["role"] == "user"]
            
            print(f"Total messages in history: {len(messages)}")
            print(f"User messages count: {len(user_messages)}")
            print(f"Assistant messages count: {len(assistant_messages)}")
            
            # The history should contain:
            # - User: "Explain recursion..." (1)
            # - Assistant: explanation (2)
            # - User: "Calculate 125 * 48." (3)
            # - Assistant: "The calculation result is 6000." (4)
            # - User: "Calculate 125 * 48." (WebSocket run) (5)
            # - Assistant: "The result is 6000." (WebSocket run) (6)
            # Total should be exactly 6 (3 user, 3 assistant), proving exactly-once persistence!
            assert len(messages) == 6
            print("[SUCCESS] Exactly-once assistant message persistence verified.")
        except Exception as e:
            print(f"[FAIL] DB Persistence verification failed: {e}")

        # 7. Clean up
        print("\nDeleting conversation to clean database...")
        r = await client.delete(f"{base_url}/conversations/{conv_id}")
        assert r.status_code == 204
        print("[SUCCESS] Conversation deleted successfully.")

if __name__ == "__main__":
    asyncio.run(run_live_agent_verification())
