import httpx
import logging
from typing import Optional
from app.services.weather.base import BaseWeatherProvider
from app.services.weather.schemas import WeatherData, DailyForecastItem, get_wmo_description
from app.services.weather.exceptions import WeatherProviderUnavailableError

logger = logging.getLogger("app.services.weather.open_meteo")

class OpenMeteoWeatherProvider(BaseWeatherProvider):
    """
    Concrete Weather Provider using Open-Meteo API.
    Does not require API keys.
    """

    async def get_weather(self, latitude: float, longitude: float, forecast_days: int) -> WeatherData:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "daily": "temperature_2m_max,temperature_2m_min,weathercode",
            "timezone": "auto",
            "forecast_days": forecast_days
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    raise WeatherProviderUnavailableError(
                        f"Open-Meteo returned status code {response.status_code}: {response.text}"
                    )
                data = response.json()
        except httpx.RequestError as e:
            raise WeatherProviderUnavailableError(f"HTTP request to Open-Meteo failed: {e}")
            
        try:
            # Parse current weather
            current = data.get("current_weather", {})
            current_temp = float(current.get("temperature", 0.0))
            current_code = int(current.get("weathercode", 0))
            
            # Parse daily forecast
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            temps_max = daily.get("temperature_2m_max", [])
            temps_min = daily.get("temperature_2m_min", [])
            codes = daily.get("weathercode", [])
            
            forecast_items = []
            # Open-Meteo can sometimes return slightly different array lengths
            limit = min(len(dates), len(temps_max), len(temps_min), len(codes), forecast_days)
            
            for i in range(limit):
                forecast_items.append(
                    DailyForecastItem(
                        date=dates[i],
                        temperature_max=float(temps_max[i]),
                        temperature_min=float(temps_min[i]),
                        weather_code=int(codes[i]),
                        description=get_wmo_description(int(codes[i]))
                    )
                )
                
            return WeatherData(
                latitude=latitude,
                longitude=longitude,
                timezone=data.get("timezone", "UTC"),
                location_name="", # to be set by the caller
                current_temp=current_temp,
                current_weather_code=current_code,
                current_description=get_wmo_description(current_code),
                daily_forecast=forecast_items
            )
        except Exception as e:
            logger.error(f"Failed to parse Open-Meteo response: {e}")
            raise WeatherProviderUnavailableError(f"Failed to parse Open-Meteo weather response: {e}")
