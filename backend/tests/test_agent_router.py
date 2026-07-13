import pytest
from unittest.mock import AsyncMock, patch
from app.agent.router import AgentRouter
from app.llm.schemas import Message as LLMMessage

@pytest.mark.asyncio
async def test_agent_router_direct_route():
    router = AgentRouter()
    context = [LLMMessage(role="user", content="Hello, write a poem")]
    
    mock_llm_response = {
        "message": {
            "role": "assistant",
            "content": '{"route": "direct", "reason_code": "NO_TOOL_REQUIRED"}'
        }
    }
    
    with patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_llm_response
        decision = await router.route(context)
        assert decision.route == "direct"
        assert decision.reason_code == "NO_TOOL_REQUIRED"
        mock_chat.assert_called_once()

@pytest.mark.asyncio
async def test_agent_router_agent_route():
    router = AgentRouter()
    context = [LLMMessage(role="user", content="Calculate 125 * 48")]
    
    mock_llm_response = {
        "message": {
            "role": "assistant",
            "content": '{"route": "agent", "reason_code": "TOOL_REQUIRED"}'
        }
    }
    
    with patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_llm_response
        decision = await router.route(context)
        assert decision.route == "agent"
        assert decision.reason_code == "TOOL_REQUIRED"

@pytest.mark.asyncio
async def test_agent_router_markdown_fences():
    router = AgentRouter()
    context = [LLMMessage(role="user", content="Calculate 125 * 48")]
    
    mock_llm_response = {
        "message": {
            "role": "assistant",
            "content": '```json\n{"route": "agent", "reason_code": "TOOL_REQUIRED"}\n```'
        }
    }
    
    with patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_llm_response
        decision = await router.route(context)
        assert decision.route == "agent"
        assert decision.reason_code == "TOOL_REQUIRED"

@pytest.mark.asyncio
async def test_agent_router_parse_retry_and_fallback():
    router = AgentRouter()
    context = [LLMMessage(role="user", content="Calculate 125 * 48")]
    
    # First response is malformed, second is correct
    mock_chat_responses = [
        {"message": {"role": "assistant", "content": "I think it is an agent route."}}, # Malformed
        {"message": {"role": "assistant", "content": '{"route": "agent", "reason_code": "TOOL_REQUIRED"}'}}
    ]
    
    with patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.side_effect = mock_chat_responses
        decision = await router.route(context)
        assert decision.route == "agent"
        assert decision.reason_code == "TOOL_REQUIRED"
        assert mock_chat.call_count == 2

@pytest.mark.asyncio
async def test_agent_router_fallback_on_complete_failure():
    router = AgentRouter()
    context = [LLMMessage(role="user", content="Calculate 125 * 48")]
    
    mock_llm_response = {
        "message": {
            "role": "assistant",
            "content": "Completely invalid text"
        }
    }
    
    with patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_llm_response
        decision = await router.route(context)
        # Should fallback to direct
        assert decision.route == "direct"
        assert decision.reason_code == "ROUTER_PARSE_FAILURE"
