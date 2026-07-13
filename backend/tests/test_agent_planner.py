import pytest
from unittest.mock import AsyncMock, patch
from app.agent.planner import AgentPlanner
from app.llm.schemas import Message as LLMMessage
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
async def test_agent_planner_valid_one_step():
    planner = AgentPlanner()
    context = [LLMMessage(role="user", content="Calculate 125 * 48")]
    
    mock_response = {
        "message": {
            "role": "assistant",
            "content": '{"goal": "Calculate expression", "steps": [{"id": 1, "description": "Calc", "tool_name": "calculator", "arguments": {"expression": "125 * 48"}}]}'
        }
    }
    
    with patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_response
        plan = await planner.plan(context)
        assert plan.goal == "Calculate expression"
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "calculator"
        assert plan.steps[0].arguments == {"expression": "125 * 48"}

@pytest.mark.asyncio
async def test_agent_planner_unknown_tool_rejected():
    planner = AgentPlanner()
    context = [LLMMessage(role="user", content="Search the web")]
    
    # Planner outputs a plan with a tool "web_search" which is not registered
    mock_response = {
        "message": {
            "role": "assistant",
            "content": '{"goal": "Search web", "steps": [{"id": 1, "description": "Search", "tool_name": "web_search", "arguments": {"query": "FastAPI"}}]}'
        }
    }
    
    with patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_response
        with pytest.raises(ValueError) as exc:
            await planner.plan(context)
        assert "Unknown tool" in str(exc.value)

@pytest.mark.asyncio
async def test_agent_planner_excessive_steps_rejected():
    planner = AgentPlanner()
    context = [LLMMessage(role="user", content="Do lots of math")]
    
    # Let's generate a plan with 9 steps, but limit is 8
    steps_list = [{"id": i, "description": f"Step {i}", "tool_name": "calculator", "arguments": {"expression": "1+1"}} for i in range(1, 10)]
    plan_json = {
        "goal": "Do 9 calculations",
        "steps": steps_list
    }
    
    json_str = str(plan_json).replace("'", '"')
    mock_response = {
        "message": {
            "role": "assistant",
            "content": json_str
        }
    }
    
    with patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_response
        with pytest.raises(ValueError) as exc:
            await planner.plan(context)
        assert "exceeds maximum step limit" in str(exc.value)

@pytest.mark.asyncio
async def test_agent_planner_invalid_arguments_rejected():
    planner = AgentPlanner()
    context = [LLMMessage(role="user", content="Echo something")]
    
    # Echo tool expects "text" parameter, but planner provides "message"
    mock_response = {
        "message": {
            "role": "assistant",
            "content": '{"goal": "Echo text", "steps": [{"id": 1, "description": "Echo", "tool_name": "echo", "arguments": {"message": "Hello"}}]}'
        }
    }
    
    with patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_response
        with pytest.raises(ValueError) as exc:
            await planner.plan(context)
        # Should fail validation on input_schema parameter validation
        assert "validation" in str(exc.value).lower() or "missing" in str(exc.value).lower()
