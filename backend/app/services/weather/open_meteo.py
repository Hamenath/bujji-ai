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
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,weathercode,precipitation_probability_max,precipitation_sum",
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
            # Parse current weather (with legacy mock fallback support)
            current = data.get("current") or data.get("current_weather") or {}
            
            current_temp = float(current.get("temperature_2m") or current.get("temperature") or 0.0)
            current_code = int(current.get("weather_code") or current.get("weathercode") or 0)
            apparent_temp = current.get("apparent_temperature")
            if apparent_temp is not None:
                apparent_temp = float(apparent_temp)
            relative_humidity = current.get("relative_humidity_2m")
            if relative_humidity is not None:
                relative_humidity = float(relative_humidity)
            wind_speed = current.get("wind_speed_10m") or current.get("windspeed")
            if wind_speed is not None:
                wind_speed = float(wind_speed)
            precipitation = current.get("precipitation")
            if precipitation is not None:
                precipitation = float(precipitation)
            observation_time = current.get("time")
            
            # Parse daily forecast
            daily = data.get("daily", {})
            dates = daily.get("time", [])
            temps_max = daily.get("temperature_2m_max", [])
            temps_min = daily.get("temperature_2m_min", [])
            codes = daily.get("weathercode") or daily.get("weather_code") or []
            precip_prob = daily.get("precipitation_probability_max") or [None] * len(dates)
            precip_sum = daily.get("precipitation_sum") or [None] * len(dates)
            
            forecast_items = []
            # Open-Meteo can sometimes return slightly different array lengths
            limit = min(len(dates), len(temps_max), len(temps_min), len(codes), forecast_days)
            
            for i in range(limit):
                prob = precip_prob[i] if i < len(precip_prob) else None
                if prob is not None:
                    prob = float(prob)
                psum = precip_sum[i] if i < len(precip_sum) else None
                if psum is not None:
                    psum = float(psum)
                forecast_items.append(
                    DailyForecastItem(
                        date=dates[i],
                        temperature_max=float(temps_max[i]),
                        temperature_min=float(temps_min[i]),
                        weather_code=int(codes[i]),
                        description=get_wmo_description(int(codes[i])),
                        precipitation_probability=prob,
                        precipitation_sum=psum
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
                apparent_temperature=apparent_temp,
                relative_humidity=relative_humidity,
                wind_speed=wind_speed,
                precipitation=precipitation,
                observation_time=observation_time,
                daily_forecast=forecast_items
            )
        except Exception as e:
            logger.error(f"Failed to parse Open-Meteo response: {e}")
            raise WeatherProviderUnavailableError(f"Failed to parse Open-Meteo weather response: {e}")
