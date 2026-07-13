import pytest
import json
from unittest.mock import AsyncMock, patch
from app.agent.orchestrator import AgentOrchestrator
from app.agent.schemas import RouterDecision, ActionPlan, PlanStep
from app.tools.registry import tool_registry
from app.tools.internal.weather import WeatherTool
from app.tools.internal.world_time import WorldTimeTool
from app.tools.internal.unit_converter import UnitConverterTool
from app.tools.internal.date_calculator import DateCalculatorTool
from app.llm.schemas import Message as LLMMessage

@pytest.fixture(autouse=True)
def setup_tools():
    tool_registry.clear()
    tool_registry.register(WeatherTool())
    tool_registry.register(WorldTimeTool())
    tool_registry.register(UnitConverterTool())
    tool_registry.register(DateCalculatorTool())
    yield
    tool_registry.clear()

@pytest.mark.asyncio
async def test_agent_orchestrator_weather_flow():
    orchestrator = AgentOrchestrator()
    context = [LLMMessage(role="user", content="What is the weather in New York?")]
    
    mock_router_decision = RouterDecision(route="agent", reason_code="TOOL_REQUIRED")
    mock_plan = ActionPlan(
        goal="Get weather for New York",
        steps=[
            PlanStep(
                id=1,
                description="Fetch weather",
                tool_name="weather",
                arguments={"location": "New York", "forecast_days": 1, "units": "imperial"}
            )
        ]
    )

    mock_weather_data = {
        "location": "New York, US",
        "latitude": 40.7128,
        "longitude": -74.006,
        "timezone": "America/New_York",
        "current_weather": {
            "temperature": 75.0,
            "unit": "F",
            "weather_code": 0,
            "description": "Clear sky"
        },
        "forecast": []
    }

    mock_final_response = {
        "message": {"role": "assistant", "content": "The weather in New York is currently Clear sky and 75°F."}
    }

    with patch("app.agent.router.agent_router.route", new_callable=AsyncMock) as mock_route, \
         patch("app.agent.planner.agent_planner.plan", new_callable=AsyncMock) as mock_plan_call, \
         patch("app.services.weather.open_meteo.OpenMeteoWeatherProvider.get_weather", new_callable=AsyncMock) as mock_weather_provider, \
         patch("app.services.weather.geocoding.geocoding_service.resolve", new_callable=AsyncMock) as mock_geocoder, \
         patch("app.services.chat_service.chat_service.get_chat_completion", new_callable=AsyncMock) as mock_chat:
        
        mock_route.return_value = mock_router_decision
        mock_plan_call.return_value = mock_plan
        mock_geocoder.return_value = AsyncMock(latitude=40.7128, longitude=-74.006, timezone="America/New_York", name="New York", country="US")
        mock_weather_provider.return_value = AsyncMock(current_temp=23.9, current_weather_code=0, current_description="Clear sky", timezone="America/New_York", daily_forecast=[])
        mock_chat.return_value = mock_final_response
        
        events = []
        async for event_type, event_data in orchestrator.execute("conv_id", "What is the weather in New York?", context, stream=False):
            events.append((event_type, event_data))
            
        assert events[0][0] == "agent.started"
        assert events[1][0] == "agent.route.selected"
        assert events[2][0] == "agent.plan.created"
        assert events[3][0] == "tool.started"
        assert events[3][1]["tool_name"] == "weather"
        assert events[4][0] == "tool.completed"
        assert events[4][1]["result"]["current_weather"]["temperature"] == 75.0
        assert events[5][0] == "response.chunk"
        assert events[6][0] == "agent.completed"
        assert "75°F" in events[6][1]["final_response"]
