import pytest
import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from app.tools.internal.weather import WeatherTool
from app.tools.internal.world_time import WorldTimeTool
from app.tools.internal.unit_converter import UnitConverterTool
from app.tools.internal.date_calculator import DateCalculatorTool
from app.services.weather.schemas import GeocodingResult, WeatherData, DailyForecastItem
from app.services.weather.cache import weather_cache

@pytest.fixture(autouse=True)
def clear_caches():
    weather_cache.clear()
    yield
    weather_cache.clear()

# --- WEATHER TOOL TESTS ---

@pytest.mark.asyncio
async def test_weather_tool_coordinates_metric():
    tool = WeatherTool()
    
    mock_weather = WeatherData(
        latitude=48.8566,
        longitude=2.3522,
        timezone="Europe/Paris",
        location_name="",
        current_temp=15.0,
        current_weather_code=0,
        current_description="Clear sky",
        daily_forecast=[
            DailyForecastItem(date="2026-07-13", temperature_max=20.0, temperature_min=10.0, weather_code=0, description="Clear sky")
        ]
    )

    with patch("app.services.weather.open_meteo.OpenMeteoWeatherProvider.get_weather", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_weather
        
        result = await tool.execute(latitude=48.8566, longitude=2.3522, forecast_days=1, units="metric")
        assert result.success is True
        assert result.data is not None
        assert result.data["location"] == "48.8566,2.3522"
        assert result.data["current_weather"]["temperature"] == 15.0
        assert result.data["current_weather"]["unit"] == "C"
        assert result.data["forecast"][0]["temperature_max"] == 20.0

@pytest.mark.asyncio
async def test_weather_tool_location_imperial():
    tool = WeatherTool()
    
    mock_geo = GeocodingResult(name="Paris", latitude=48.8566, longitude=2.3522, timezone="Europe/Paris", country="France")
    mock_weather = WeatherData(
        latitude=48.8566,
        longitude=2.3522,
        timezone="Europe/Paris",
        location_name="",
        current_temp=10.0,  # 10C = 50F
        current_weather_code=3,
        current_description="Overcast",
        daily_forecast=[
            DailyForecastItem(date="2026-07-13", temperature_max=15.0, temperature_min=5.0, weather_code=3, description="Overcast")
        ]
    )

    with patch("app.services.weather.geocoding.geocoding_service.resolve", new_callable=AsyncMock) as mock_geo_call, \
         patch("app.services.weather.open_meteo.OpenMeteoWeatherProvider.get_weather", new_callable=AsyncMock) as mock_weather_call:
        
        mock_geo_call.return_value = mock_geo
        mock_weather_call.return_value = mock_weather
        
        result = await tool.execute(location="Paris", forecast_days=1, units="imperial")
        assert result.success is True
        assert result.data is not None
        assert "Paris" in result.data["location"]
        assert result.data["current_weather"]["temperature"] == 50.0  # 10C -> 50F
        assert result.data["current_weather"]["unit"] == "F"
        assert result.data["forecast"][0]["temperature_max"] == 59.0  # 15C -> 59F

@pytest.mark.asyncio
async def test_weather_tool_invalid_args():
    tool = WeatherTool()
    result = await tool.execute()  # missing coordinates and location name
    assert result.success is False
    assert result.error == "INVALID_ARGUMENTS"

# --- WORLD TIME TOOL TESTS ---

@pytest.mark.asyncio
async def test_world_time_timezone_direct():
    tool = WorldTimeTool()
    
    result = await tool.execute(timezone_or_city="Europe/London")
    assert result.success is True
    assert result.data is not None
    assert result.data["timezone"] == "Europe/London"
    assert "Europe/London" in result.data["location"]
    assert result.data["current_time"] is not None

@pytest.mark.asyncio
async def test_world_time_city_geocoded():
    tool = WorldTimeTool()
    
    mock_geo = GeocodingResult(name="Tokyo", latitude=35.6895, longitude=139.6917, timezone="Asia/Tokyo", country="Japan")
    
    with patch("app.services.weather.geocoding.geocoding_service.resolve", new_callable=AsyncMock) as mock_geo_call:
        mock_geo_call.return_value = mock_geo
        
        result = await tool.execute(timezone_or_city="Tokyo")
        assert result.success is True
        assert result.data is not None
        assert "Tokyo" in result.data["location"]
        assert result.data["timezone"] == "Asia/Tokyo"
        assert result.data["current_time"] is not None

# --- UNIT CONVERTER TESTS ---

@pytest.mark.asyncio
async def test_unit_converter_temperature():
    tool = UnitConverterTool()
    
    # 0C -> 32F
    res = await tool.execute(value=0, from_unit="celsius", to_unit="fahrenheit")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 32.0
    
    # 100C -> 373.15K
    res = await tool.execute(value=100, from_unit="c", to_unit="kelvin")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 373.15
    
    # 50F -> 10C
    res = await tool.execute(value=50, from_unit="fahrenheit", to_unit="celsius")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 10.0

@pytest.mark.asyncio
async def test_unit_converter_length():
    tool = UnitConverterTool()
    
    # 1 mile -> 1.6093 km
    res = await tool.execute(value=1, from_unit="miles", to_unit="kilometers")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 1.6093
    
    # 10 feet -> 120 inches (1 ft = 12 inches)
    res = await tool.execute(value=10, from_unit="feet", to_unit="inches")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 120.0

@pytest.mark.asyncio
async def test_unit_converter_weight():
    tool = UnitConverterTool()
    
    # 1 kg -> 2.2046 lbs
    res = await tool.execute(value=1, from_unit="kg", to_unit="pounds")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 2.2046

@pytest.mark.asyncio
async def test_unit_converter_speed():
    tool = UnitConverterTool()
    
    # 100 kmh -> 62.1371 mph
    res = await tool.execute(value=100, from_unit="kmh", to_unit="mph")
    assert res.success is True
    assert res.data is not None
    assert res.data["result"] == 62.1371

@pytest.mark.asyncio
async def test_unit_converter_errors():
    tool = UnitConverterTool()
    
    # Incompatible categories (temperature to length)
    res = await tool.execute(value=10, from_unit="celsius", to_unit="meters")
    assert res.success is False
    assert res.error == "INVALID_ARGUMENTS"

# --- DATE CALCULATOR TESTS ---

@pytest.mark.asyncio
async def test_date_calculator_difference():
    tool = DateCalculatorTool()
    
    # Difference between 2026-07-13 and 2026-07-20 (7 days, 1 week)
    res = await tool.execute(operation="difference", start_date="2026-07-13", end_date="2026-07-20")
    assert res.success is True
    assert res.data is not None
    assert res.data["difference_days"] == 7
    assert res.data["difference_weeks"] == 1.0

@pytest.mark.asyncio
async def test_date_calculator_add_subtract():
    tool = DateCalculatorTool()
    
    # Add 15 days to 2026-07-13 -> 2026-07-28
    res = await tool.execute(operation="add_subtract", start_date="2026-07-13", amount=15, unit="days")
    assert res.success is True
    assert res.data is not None
    assert res.data["result_date"] == "2026-07-28"
    
    # Subtract 2 weeks from 2026-07-13 -> 2026-06-29
    res = await tool.execute(operation="add_subtract", start_date="2026-07-13", amount=-2, unit="weeks")
    assert res.success is True
    assert res.data is not None
    assert res.data["result_date"] == "2026-06-29"

@pytest.mark.asyncio
async def test_date_calculator_leap_year():
    tool = DateCalculatorTool()
    
    # Feb 28, 2024 (leap year) + 1 day -> Feb 29, 2024
    res = await tool.execute(operation="add_subtract", start_date="2024-02-28", amount=1, unit="days")
    assert res.success is True
    assert res.data is not None
    assert res.data["result_date"] == "2024-02-29"
    
    # Feb 29, 2024 + 1 year -> Feb 28, 2025 (non-leap year edge case)
    res = await tool.execute(operation="add_subtract", start_date="2024-02-29", amount=1, unit="years")
    assert res.success is True
    assert res.data is not None
    assert res.data["result_date"] == "2025-02-28"
