import pytest
from unittest.mock import AsyncMock, patch
from fastapi import status
from app.database.repositories.conversation_repository import conversation_repo
from app.database.repositories.message_repository import message_repo
from app.database.repositories.agent_run_repository import agent_run_repo
from app.database.repositories.tool_execution_repository import tool_execution_repo
from app.agent.schemas import RouterDecision, ActionPlan, PlanStep
from app.tools.registry import tool_registry
from app.tools.internal.calculator import CalculatorTool

@pytest.fixture(autouse=True)
def setup_tools():
    tool_registry.clear()
    tool_registry.register(CalculatorTool())
    yield
    tool_registry.clear()

def test_rest_agent_unauthorized_conversation(client):
    payload = {"content": "Hello"}
    response = client.post("/api/v1/conversations/nonexistent_conv_id/agent", json=payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()

def test_rest_agent_direct_flow_success(client, db_session):
    # 1. Create a conversation
    conv = conversation_repo.create(db_session, "Direct Test")
    
    mock_router_decision = RouterDecision(route="direct", reason_code="NO_TOOL_REQUIRED")
    mock_direct_response = {
        "message": {"role": "assistant", "content": "This is a direct response."}
    }
    
    with patch("app.agent.router.agent_router.route", new_callable=AsyncMock) as mock_route, \
         patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        
        mock_route.return_value = mock_router_decision
        mock_chat.return_value = mock_direct_response
        
        payload = {"content": "Tell me a joke"}
        response = client.post(f"/api/v1/conversations/{conv.id}/agent", json=payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["conversation_id"] == conv.id
        assert data["route"] == "direct"
        assert data["status"] == "completed"
        assert data["response"] == "This is a direct response."
        assert len(data["steps"]) == 0
        
        # Verify message count in database: 1 user, 1 assistant (Exactly-once persistence)
        msgs = message_repo.list_by_conversation(db_session, conv.id)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[0].content == "Tell me a joke"
        assert msgs[1].role == "assistant"
        assert msgs[1].content == "This is a direct response."
        
        # Verify AgentRun record exists
        runs = agent_run_repo.list_by_conversation(db_session, conv.id)
        assert len(runs) == 1
        assert runs[0].route == "direct"
        assert runs[0].status == "completed"
        assert runs[0].user_message_id == msgs[0].id
        assert runs[0].assistant_message_id == msgs[1].id

def test_rest_agent_tool_flow_success(client, db_session):
    conv = conversation_repo.create(db_session, "Tool Test")
    
    mock_router_decision = RouterDecision(route="agent", reason_code="TOOL_REQUIRED")
    mock_plan = ActionPlan(
        goal="Calculate the math",
        steps=[
            PlanStep(id=1, description="Calculate", tool_name="calculator", arguments={"expression": "125 * 48"})
        ]
    )
    mock_final_response = {
        "message": {"role": "assistant", "content": "The calculation result is 6000."}
    }
    
    with patch("app.agent.router.agent_router.route", new_callable=AsyncMock) as mock_route, \
         patch("app.agent.planner.agent_planner.plan", new_callable=AsyncMock) as mock_plan_call, \
         patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        
        mock_route.return_value = mock_router_decision
        mock_plan_call.return_value = mock_plan
        mock_chat.return_value = mock_final_response
        
        payload = {"content": "Calculate 125 * 48"}
        response = client.post(f"/api/v1/conversations/{conv.id}/agent", json=payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["conversation_id"] == conv.id
        assert data["route"] == "agent"
        assert data["status"] == "completed"
        assert data["response"] == "The calculation result is 6000."
        assert len(data["steps"]) == 1
        assert data["steps"][0]["tool_name"] == "calculator"
        assert data["steps"][0]["success"] is True
        
        # Verify message count in database: 1 user, 1 assistant (Exactly-once persistence)
        msgs = message_repo.list_by_conversation(db_session, conv.id)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        
        # Verify AgentRun record exists
        runs = agent_run_repo.list_by_conversation(db_session, conv.id)
        assert len(runs) == 1
        assert runs[0].route == "agent"
        assert runs[0].status == "completed"
        
        # Verify ToolExecution record exists
        executions = tool_execution_repo.list_by_run(db_session, runs[0].id)
        assert len(executions) == 1
        assert executions[0].tool_name == "calculator"
        assert executions[0].success is True
        assert "125 * 48" in executions[0].arguments_json
