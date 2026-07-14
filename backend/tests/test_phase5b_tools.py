import pytest
import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from zoneinfo import ZoneInfo
from app.tools.registry import tool_registry
from app.tools.internal.world_time import WorldTimeTool
from app.tools.internal.unit_converter import UnitConverterTool
from app.tools.internal.date_calculator import DateCalculatorTool
from app.services.weather.schemas import WeatherData, GeocodingResult, DailyForecastItem
from app.services.weather.cache import weather_cache

@pytest.fixture(autouse=True)
def clear_caches():
    weather_cache.clear()
    yield
    weather_cache.clear()

# --- WORLD TIME TOOL COORDINATES LOOKUP ---

@pytest.mark.asyncio
async def test_world_time_tool_coords_fields():
    tool = WorldTimeTool()
    
    mock_weather = WeatherData(
        latitude=12.9716,
        longitude=77.5946,
        timezone="Asia/Kolkata",
        location_name="",
        current_temp=25.0,
        current_weather_code=0,
        current_description="Clear sky",
        daily_forecast=[]
    )
    
    with patch("app.services.weather.open_meteo.OpenMeteoWeatherProvider.get_weather", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_weather
        
        result = await tool.execute(latitude=12.9716, longitude=77.5946)
        assert result.success is True
        assert result.data is not None
        assert result.data["location"] == "12.9716,77.5946"
        assert result.data["timezone"] == "Asia/Kolkata"
        assert result.data["current_time"] is not None
        assert result.data["utc_offset"] in ("UTC+05:30", "UTC+05:00")  # accounting for standard format offset

@pytest.mark.asyncio
async def test_world_time_tool_coords_string():
    tool = WorldTimeTool()
    
    mock_weather = WeatherData(
        latitude=48.8566,
        longitude=2.3522,
        timezone="Europe/Paris",
        location_name="",
        current_temp=15.0,
        current_weather_code=0,
        current_description="Clear sky",
        daily_forecast=[]
    )
    
    with patch("app.services.weather.open_meteo.OpenMeteoWeatherProvider.get_weather", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_weather
        
        result = await tool.execute(timezone_or_city="48.8566, 2.3522")
        assert result.success is True
        assert result.data is not None
        assert result.data["location"] == "48.8566,2.3522"
        assert result.data["timezone"] == "Europe/Paris"

@pytest.mark.asyncio
async def test_world_time_tool_invalid_coords():
    tool = WorldTimeTool()
    result = await tool.execute(latitude=100.0, longitude=77.5946)
    assert result.success is False
    assert result.error == "INVALID_ARGUMENTS"

# --- UNIT CONVERTER EXPANSIONS ---

@pytest.mark.asyncio
async def test_unit_converter_area():
    tool = UnitConverterTool()
    
    # 1 square km to square meters = 1,000,000
    res = await tool.execute(value=1, from_unit="square_kilometers", to_unit="square_meters")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 1000000.0
    
    # 10 acres to hectares (1 ac = 4046.8564224 sq_m, 1 ha = 10000 sq_m => 10 ac = 4.046856 ha)
    res = await tool.execute(value=10, from_unit="ac", to_unit="ha")
    assert res.success is True
    assert res.data is not None
    assert abs(res.data["result"] - 4.046856) < 1e-4

@pytest.mark.asyncio
async def test_unit_converter_volume():
    tool = UnitConverterTool()
    
    # 2 liters to milliliters = 2000
    res = await tool.execute(value=2, from_unit="liters", to_unit="ml")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 2000.0
    
    # 1 gallon to quarts = 4
    res = await tool.execute(value=1, from_unit="gallons", to_unit="quarts")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 4.0

@pytest.mark.asyncio
async def test_unit_converter_digital_storage():
    tool = UnitConverterTool()
    
    # 1 megabyte to kilobytes = 1024
    res = await tool.execute(value=1, from_unit="mb", to_unit="kb")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 1024.0
    
    # 1 gigabyte to bytes = 1073741824
    res = await tool.execute(value=1, from_unit="gigabytes", to_unit="bytes")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 1073741824.0

@pytest.mark.asyncio
async def test_unit_converter_mismatched_categories():
    tool = UnitConverterTool()
    res = await tool.execute(value=10, from_unit="liters", to_unit="sq_m")
    assert res.success is False
    assert res.error == "INVALID_ARGUMENTS"

# --- DATE CALCULATOR RELATIVE KEYWORDS & TIMEZONE DATETIMES ---

@pytest.mark.asyncio
async def test_date_calculator_relative_keywords():
    tool = DateCalculatorTool()
    
    # "today" relative keyword difference with format string
    res = await tool.execute(operation="difference", start_date="today", end_date="tomorrow")
    assert res.success is True
    assert res.data is not None
    assert res.data["difference_days"] == 1
    
    # Check with specific timezone
    res = await tool.execute(operation="difference", start_date="today", end_date="yesterday", timezone="Asia/Kolkata")
    assert res.success is True
    assert res.data is not None
    assert res.data["difference_days"] == -1

@pytest.mark.asyncio
async def test_date_calculator_timezone_aware_datetimes():
    tool = DateCalculatorTool()
    
    # Diff between two timezone aware datetimes
    res = await tool.execute(
        operation="difference",
        start_date="2026-07-14T09:00:00+05:30",
        end_date="2026-07-14T12:30:00+05:30"
    )
    assert res.success is True
    assert res.data is not None
    assert res.data["difference_hours"] == 3.5
    assert res.data["difference_minutes"] == 210.0
    assert res.data["difference_seconds"] == 12600.0

@pytest.mark.asyncio
async def test_date_calculator_add_time_units():
    tool = DateCalculatorTool()
    
    # Add 90 minutes to a timezone aware datetime
    res = await tool.execute(
        operation="add_subtract",
        start_date="2026-07-14T09:00:00+05:30",
        amount=90,
        unit="minutes"
    )
    assert res.success is True
    assert res.data is not None
    assert res.data["result_date"] == "2026-07-14T10:30:00+05:30"
    
    # Subtract 2 hours
    res = await tool.execute(
        operation="add_subtract",
        start_date="2026-07-14T09:00:00+05:30",
        amount=-2,
        unit="hours"
    )
    assert res.success is True
    assert res.data is not None
    assert res.data["result_date"] == "2026-07-14T07:00:00+05:30"

@pytest.mark.asyncio
async def test_date_calculator_invalid_timezone():
    tool = DateCalculatorTool()
    res = await tool.execute(operation="difference", start_date="today", end_date="tomorrow", timezone="Invalid/Timezone")
    assert res.success is False
    assert res.error == "INVALID_ARGUMENTS"

# --- TOOL REGISTRY CHECKS ---

def test_new_weather_tools_registered():
    geocode_tool = tool_registry.get_tool("geocode_place")
    current_tool = tool_registry.get_tool("weather_current")
    forecast_tool = tool_registry.get_tool("weather_forecast")
    
    assert geocode_tool is not None
    assert current_tool is not None
    assert forecast_tool is not None
    
    assert geocode_tool.name == "geocode_place"
    assert current_tool.name == "weather_current"
    assert forecast_tool.name == "weather_forecast"
