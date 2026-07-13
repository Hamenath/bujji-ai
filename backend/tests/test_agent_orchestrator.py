import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.config import settings
from app.llm.schemas import Message as LLMMessage
from app.agent.orchestrator import AgentOrchestrator
from app.agent.schemas import RouterDecision, ActionPlan, PlanStep
from app.tools.registry import tool_registry
from app.tools.internal.echo import EchoTool
from app.tools.internal.calculator import CalculatorTool

@pytest.fixture(autouse=True)
def setup_tools():
    tool_registry.clear()
    tool_registry.register(EchoTool())
    tool_registry.register(CalculatorTool())
    yield
    tool_registry.clear()

@pytest.mark.asyncio
async def test_orchestrator_direct_route():
    orchestrator = AgentOrchestrator()
    context = [LLMMessage(role="user", content="Hello")]
    
    mock_router_decision = RouterDecision(route="direct", reason_code="NO_TOOL_REQUIRED")
    mock_direct_response = {
        "message": {"role": "assistant", "content": "Hello, how can I help you today?"}
    }
    
    with patch("app.agent.router.agent_router.route", new_callable=AsyncMock) as mock_route, \
         patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        
        mock_route.return_value = mock_router_decision
        mock_chat.return_value = mock_direct_response
        
        events = []
        async for event_type, event_data in orchestrator.execute("conv_id", "Hello", context, stream=False):
            events.append((event_type, event_data))
            
        assert events[0][0] == "agent.started"
        assert events[1][0] == "agent.route.selected"
        assert events[1][1]["route"] == "direct"
        assert events[2][0] == "response.chunk"
        assert events[3][0] == "agent.completed"
        assert events[3][1]["final_response"] == "Hello, how can I help you today?"

@pytest.mark.asyncio
async def test_orchestrator_one_step_tool_route():
    orchestrator = AgentOrchestrator()
    context = [LLMMessage(role="user", content="Calculate 125 * 48")]
    
    mock_router_decision = RouterDecision(route="agent", reason_code="TOOL_REQUIRED")
    mock_plan = ActionPlan(
        goal="Calculate a mathematical expression",
        steps=[
            PlanStep(id=1, description="Do math", tool_name="calculator", arguments={"expression": "125 * 48"})
        ]
    )
    mock_final_response = {
        "message": {"role": "assistant", "content": "The result is 6000."}
    }
    
    with patch("app.agent.router.agent_router.route", new_callable=AsyncMock) as mock_route, \
         patch("app.agent.planner.agent_planner.plan", new_callable=AsyncMock) as mock_plan_call, \
         patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        
        mock_route.return_value = mock_router_decision
        mock_plan_call.return_value = mock_plan
        mock_chat.return_value = mock_final_response
        
        events = []
        async for event_type, event_data in orchestrator.execute("conv_id", "Calculate 125 * 48", context, stream=False):
            events.append((event_type, event_data))
            
        assert events[0][0] == "agent.started"
        assert events[1][0] == "agent.route.selected"
        assert events[2][0] == "agent.plan.created"
        assert events[3][0] == "tool.started"
        assert events[4][0] == "tool.completed"
        assert events[4][1]["step_number"] == 1
        assert events[4][1]["success"] is True
        assert events[5][0] == "response.chunk"
        assert events[6][0] == "agent.completed"
        assert events[6][1]["final_response"] == "The result is 6000."

@pytest.mark.asyncio
async def test_orchestrator_loop_prevention():
    orchestrator = AgentOrchestrator()
    context = [LLMMessage(role="user", content="Repeat echo")]
    
    mock_router_decision = RouterDecision(route="agent", reason_code="TOOL_REQUIRED")
    # Plan has duplicate steps (same tool, same arguments) to check loop prevention
    mock_plan = ActionPlan(
        goal="Demonstrate loop detection",
        steps=[
            PlanStep(id=1, description="Step 1", tool_name="echo", arguments={"text": "hello"}),
            PlanStep(id=2, description="Step 2", tool_name="echo", arguments={"text": "hello"}),
            PlanStep(id=3, description="Step 3", tool_name="echo", arguments={"text": "hello"})
        ]
    )
    
    with patch("app.agent.router.agent_router.route", new_callable=AsyncMock) as mock_route, \
         patch("app.agent.planner.agent_planner.plan", new_callable=AsyncMock) as mock_plan_call:
        
        mock_route.return_value = mock_router_decision
        mock_plan_call.return_value = mock_plan
        
        events = []
        async for event_type, event_data in orchestrator.execute("conv_id", "Repeat echo", context, stream=False):
            events.append((event_type, event_data))
            
        # Should execute step 1 and step 2, but step 3 will violate duplicate action limit (AGENT_MAX_DUPLICATE_ACTIONS=1)
        # So we should see agent.failed event with DUPLICATE_ACTION_DETECTED
        failed_event = events[-1]
        assert failed_event[0] == "agent.failed"
        assert failed_event[1]["error_code"] == "DUPLICATE_ACTION_DETECTED"
