from typing import Optional, Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult
from app.services.weather.geocoding import geocoding_service
from app.services.weather.open_meteo import OpenMeteoWeatherProvider
from app.services.weather.cache import weather_cache
from app.services.weather.exceptions import WeatherException

class WeatherInput(BaseModel):
    location: Optional[str] = Field(default=None, description="The city or place name (e.g. 'London', 'Paris').")
    latitude: Optional[float] = Field(default=None, description="Direct latitude coordinate.")
    longitude: Optional[float] = Field(default=None, description="Direct longitude coordinate.")
    forecast_days: int = Field(default=3, ge=1, le=7, description="Number of days of daily forecast to include (1-7).")
    units: str = Field(default="metric", description="Unit system: 'metric' (Celsius, km/h) or 'imperial' (Fahrenheit, mph).")

class WeatherTool(BaseTool):
    name: str = "weather"
    description: str = (
        "Get current weather and daily temperature forecast for a location (city or coordinates). "
        "Returns current temperature, WMO weather codes, descriptions, and a daily forecast."
    )
    input_schema: Any = WeatherInput
    permission_level: str = "safe"
    timeout_seconds: int = 15

    def __init__(self):
        super().__init__()
        self._provider = OpenMeteoWeatherProvider()

    async def execute(
        self,
        location: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        forecast_days: int = 3,
        units: str = "metric",
        **kwargs
    ) -> ToolResult:
        
        if not location and (latitude is None or longitude is None):
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": "Either 'location' or both 'latitude' and 'longitude' must be provided."}
            )

        resolved_lat = latitude
        resolved_lon = longitude
        resolved_name = location or f"{latitude},{longitude}"
        
        # 1. Resolve geocoding if location name is given
        if location:
            # Check geocoding cache
            geo_res = weather_cache.get_geocoding(location)
            if not geo_res:
                try:
                    geo_res = await geocoding_service.resolve(location)
                    weather_cache.set_geocoding(location, geo_res)
                except WeatherException as we:
                    return ToolResult(
                        success=False,
                        error=we.code,
                        metadata={"error_detail": str(we)}
                    )
                except Exception as e:
                    return ToolResult(
                        success=False,
                        error="GEOCODING_FAILED",
                        metadata={"error_detail": str(e)}
                    )
            resolved_lat = geo_res.latitude
            resolved_lon = geo_res.longitude
            resolved_name = f"{geo_res.name}, {geo_res.country or ''}".strip(", ")

        # 2. Query weather (with cache)
        assert resolved_lat is not None and resolved_lon is not None
        weather_data = weather_cache.get_weather(resolved_lat, resolved_lon, forecast_days)
        if not weather_data:
            try:
                weather_data = await self._provider.get_weather(resolved_lat, resolved_lon, forecast_days)
                weather_cache.set_weather(resolved_lat, resolved_lon, forecast_days, weather_data)
            except WeatherException as we:
                return ToolResult(
                    success=False,
                    error=we.code,
                    metadata={"error_detail": str(we)}
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    error="WEATHER_FETCH_FAILED",
                    metadata={"error_detail": str(e)}
                )

        # 3. Handle Celsius -> Fahrenheit conversion if "imperial" units requested
        final_temp = weather_data.current_temp
        if units.lower() == "imperial":
            final_temp = round((final_temp * 9 / 5) + 32, 1)

        forecast_list = []
        for item in weather_data.daily_forecast:
            t_max = item.temperature_max
            t_min = item.temperature_min
            if units.lower() == "imperial":
                t_max = round((t_max * 9 / 5) + 32, 1)
                t_min = round((t_min * 9 / 5) + 32, 1)
            forecast_list.append({
                "date": item.date,
                "temperature_max": t_max,
                "temperature_min": t_min,
                "weather_code": item.weather_code,
                "description": item.description
            })

        return ToolResult(
            success=True,
            data={
                "location": resolved_name,
                "latitude": resolved_lat,
                "longitude": resolved_lon,
                "timezone": weather_data.timezone,
                "current_weather": {
                    "temperature": final_temp,
                    "unit": "F" if units.lower() == "imperial" else "C",
                    "weather_code": weather_data.current_weather_code,
                    "description": weather_data.current_description
                },
                "forecast": forecast_list
            }
        )
