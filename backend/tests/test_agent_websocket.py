import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi import status
from app.database.repositories.conversation_repository import conversation_repo
from app.agent.schemas import RouterDecision, ActionPlan, PlanStep
from app.tools.registry import tool_registry
from app.tools.internal.calculator import CalculatorTool

@pytest.fixture(autouse=True)
def setup_tools():
    tool_registry.clear()
    tool_registry.register(CalculatorTool())
    yield
    tool_registry.clear()

def test_websocket_agent_run_flow(client, db_session):
    # 1. Create a conversation
    conv = conversation_repo.create(db_session, "WebSocket Agent Test")
    
    mock_router_decision = RouterDecision(route="agent", reason_code="TOOL_REQUIRED")
    mock_plan = ActionPlan(
        goal="Calculate",
        steps=[
            PlanStep(id=1, description="Math", tool_name="calculator", arguments={"expression": "100 + 50"})
        ]
    )
    
    async def mock_chat_generator(*args, **kwargs):
        chunks = [
            {"message": {"role": "assistant", "content": "The "}, "model": "llama3.2", "done": False},
            {"message": {"role": "assistant", "content": "result is 150."}, "model": "llama3.2", "done": True}
        ]
        for chunk in chunks:
            yield chunk

    with patch("app.agent.router.agent_router.route", new_callable=AsyncMock) as mock_route, \
         patch("app.agent.planner.agent_planner.plan", new_callable=AsyncMock) as mock_plan_call, \
         patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        
        mock_route.return_value = mock_router_decision
        mock_plan_call.return_value = mock_plan
        mock_chat.return_value = mock_chat_generator()
        
        # Connect to WebSocket
        with client.websocket_connect(f"/api/v1/ws/chat/{conv.id}") as websocket:
            # Receive connection.ready
            event = websocket.receive_json()
            assert event["type"] == "connection.ready"
            
            # Send agent.run event
            websocket.send_json({
                "type": "agent.run",
                "data": {"content": "Calculate 100 + 50"}
            })
            
            # 1. message.user.saved
            event = websocket.receive_json()
            assert event["type"] == "message.user.saved"
            
            # 2. agent.started
            event = websocket.receive_json()
            assert event["type"] == "agent.started"
            
            # 3. agent.route.selected
            event = websocket.receive_json()
            assert event["type"] == "agent.route.selected"
            assert event["data"]["route"] == "agent"
            
            # 4. agent.plan.created
            event = websocket.receive_json()
            assert event["type"] == "agent.plan.created"
            assert len(event["data"]["steps"]) == 1
            
            # 5. tool.started
            event = websocket.receive_json()
            assert event["type"] == "tool.started"
            
            # 6. tool.completed
            event = websocket.receive_json()
            assert event["type"] == "tool.completed"
            assert event["data"]["success"] is True
            
            # 7. response.chunk ("The ")
            event = websocket.receive_json()
            assert event["type"] == "response.chunk"
            assert event["data"]["content"] == "The "
            
            # 8. response.chunk ("result is 150.")
            event = websocket.receive_json()
            assert event["type"] == "response.chunk"
            assert event["data"]["content"] == "result is 150."
            
            # 9. agent.completed
            event = websocket.receive_json()
            assert event["type"] == "agent.completed"
            assert event["data"]["status"] == "completed"
            assert event["data"]["final_response"] == "The result is 150."

def test_websocket_agent_cancellation(client, db_session):
    conv = conversation_repo.create(db_session, "WebSocket Cancel Test")
    
    mock_router_decision = RouterDecision(route="agent", reason_code="TOOL_REQUIRED")
    mock_plan = ActionPlan(
        goal="Calculate",
        steps=[
            PlanStep(id=1, description="Math", tool_name="calculator", arguments={"expression": "100 + 50"})
        ]
    )
    
    # We want final response generation to take some time so we can cancel it
    async def mock_chat_generator_slow(*args, **kwargs):
        yield {"message": {"role": "assistant", "content": "Thinking "}, "model": "llama3.2", "done": False}
        await asyncio.sleep(2)
        yield {"message": {"role": "assistant", "content": "hard..."}, "model": "llama3.2", "done": True}

    with patch("app.agent.router.agent_router.route", new_callable=AsyncMock) as mock_route, \
         patch("app.agent.planner.agent_planner.plan", new_callable=AsyncMock) as mock_plan_call, \
         patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        
        mock_route.return_value = mock_router_decision
        mock_plan_call.return_value = mock_plan
        mock_chat.return_value = mock_chat_generator_slow()
        
        with client.websocket_connect(f"/api/v1/ws/chat/{conv.id}") as websocket:
            websocket.receive_json()  # connection.ready
            
            websocket.send_json({
                "type": "agent.run",
                "data": {"content": "Calculate 100 + 50"}
            })
            
            websocket.receive_json()  # message.user.saved
            
            # Receive agent.started and extract run_id
            agent_started = websocket.receive_json()
            assert agent_started["type"] == "agent.started"
            run_id = agent_started["data"]["run_id"]
            
            websocket.receive_json()  # agent.route.selected
            websocket.receive_json()  # agent.plan.created
            websocket.receive_json()  # tool.started
            websocket.receive_json()  # tool.completed
            
            # Send cancellation
            websocket.send_json({
                "type": "agent.cancel",
                "data": {"run_id": run_id}
            })
            
            # We should receive agent.failed event with AGENT_CANCELLED error code
            # Note: We might receive "response.chunk" (the first chunk) before the cancellation is processed.
            # So let's loop and wait for the failure event
            cancelled_received = False
            for _ in range(5):
                event = websocket.receive_json()
                if event["type"] == "agent.failed":
                    assert event["data"]["error_code"] == "AGENT_CANCELLED"
                    cancelled_received = True
                    break
            
            assert cancelled_received is True
