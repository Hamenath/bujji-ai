import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.weather.geocoding import geocoding_service
from app.services.weather.open_meteo import OpenMeteoWeatherProvider
from app.services.weather.cache import weather_cache
from app.services.weather.schemas import GeocodingResult, WeatherData
from app.services.weather.exceptions import LocationNotFoundError, WeatherProviderUnavailableError

@pytest.mark.asyncio
async def test_geocoding_service_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "name": "Paris",
                "latitude": 48.8566,
                "longitude": 2.3522,
                "timezone": "Europe/Paris",
                "country": "France",
                "admin1": "Île-de-France"
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await geocoding_service.resolve("Paris")
        assert res.name == "Paris"
        assert res.latitude == 48.8566
        assert res.longitude == 2.3522
        assert res.timezone == "Europe/Paris"
        assert res.country == "France"

@pytest.mark.asyncio
async def test_geocoding_service_not_found():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LocationNotFoundError):
            await geocoding_service.resolve("NonExistentCityNameXYZ")

@pytest.mark.asyncio
async def test_open_meteo_provider_success():
    provider = OpenMeteoWeatherProvider()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "timezone": "Europe/Paris",
        "current_weather": {
            "temperature": 18.5,
            "weathercode": 3
        },
        "daily": {
            "time": ["2026-07-13", "2026-07-14"],
            "temperature_2m_max": [22.0, 24.5],
            "temperature_2m_min": [12.0, 14.0],
            "weathercode": [3, 0]
        }
    }

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await provider.get_weather(48.8566, 2.3522, 2)
        assert res.current_temp == 18.5
        assert res.timezone == "Europe/Paris"
        assert len(res.daily_forecast) == 2
        assert res.daily_forecast[0].temperature_max == 22.0
        assert res.daily_forecast[0].description == "Overcast"
        assert res.daily_forecast[1].description == "Clear sky"

def test_weather_cache_geocoding():
    weather_cache.clear()
    
    geo = GeocodingResult(
        name="London",
        latitude=51.5074,
        longitude=-0.1278,
        timezone="Europe/London"
    )
    
    # Not present initially
    assert weather_cache.get_geocoding("London") is None
    
    # Store
    weather_cache.set_geocoding("London", geo, ttl=10)
    
    # Retrieve
    cached = weather_cache.get_geocoding("London")
    assert cached is not None
    assert cached.name == "London"
    assert cached.latitude == 51.5074
    
    # Case insensitivity
    cached_lower = weather_cache.get_geocoding("london")
    assert cached_lower is not None
    
    # Expiry
    weather_cache.set_geocoding("London", geo, ttl=-1)
    assert weather_cache.get_geocoding("London") is None
