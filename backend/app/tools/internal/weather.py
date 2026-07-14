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

class GeocodePlaceInput(BaseModel):
    place: str = Field(..., description="The place or city name to resolve coordinates for (e.g. 'Madurai', 'Paris').")

class GeocodePlaceTool(BaseTool):
    name: str = "geocode_place"
    description: str = "Resolve a place or city name into latitude, longitude, and timezone info."
    input_schema: Any = GeocodePlaceInput
    permission_level: str = "safe"
    timeout_seconds: int = 15

    async def execute(self, place: str, **kwargs) -> ToolResult:
        if not place.strip():
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": "Place name cannot be empty."}
            )
        geo_res = weather_cache.get_geocoding(place)
        if not geo_res:
            try:
                geo_res = await geocoding_service.resolve(place)
                weather_cache.set_geocoding(place, geo_res)
            except WeatherException as we:
                return ToolResult(success=False, error=we.code, metadata={"error_detail": str(we)})
            except Exception as e:
                return ToolResult(success=False, error="GEOCODING_FAILED", metadata={"error_detail": str(e)})

        return ToolResult(
            success=True,
            data={
                "latitude": geo_res.latitude,
                "longitude": geo_res.longitude,
                "timezone": geo_res.timezone,
                "name": geo_res.name,
                "country": geo_res.country,
                "admin1": geo_res.admin1
            }
        )

class WeatherCurrentInput(BaseModel):
    latitude: float = Field(..., description="Latitude coordinate.")
    longitude: float = Field(..., description="Longitude coordinate.")
    units: str = Field(default="metric", description="Unit system: 'metric' (Celsius, km/h) or 'imperial' (Fahrenheit, mph).")

class WeatherCurrentTool(BaseTool):
    name: str = "weather_current"
    description: str = "Get current weather conditions (temperature, feels-like, humidity, wind speed, precipitation) for given latitude and longitude coordinates."
    input_schema: Any = WeatherCurrentInput
    permission_level: str = "safe"
    timeout_seconds: int = 15

    async def execute(self, latitude: float, longitude: float, units: str = "metric", **kwargs) -> ToolResult:
        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": "Latitude must be between -90 and 90, and longitude between -180 and 180."}
            )
        weather_data = weather_cache.get_weather(latitude, longitude, forecast_days=1)
        if not weather_data:
            try:
                provider = OpenMeteoWeatherProvider()
                weather_data = await provider.get_weather(latitude, longitude, forecast_days=1)
                weather_cache.set_weather(latitude, longitude, forecast_days=1, result=weather_data)
            except WeatherException as we:
                return ToolResult(success=False, error=we.code, metadata={"error_detail": str(we)})
            except Exception as e:
                return ToolResult(success=False, error="WEATHER_FETCH_FAILED", metadata={"error_detail": str(e)})

        temp = weather_data.current_temp
        apparent = weather_data.apparent_temperature
        wind = weather_data.wind_speed
        precip = weather_data.precipitation
        
        if units.lower() == "imperial":
            temp = round((temp * 9 / 5) + 32, 1)
            if apparent is not None:
                apparent = round((apparent * 9 / 5) + 32, 1)
            if wind is not None:
                wind = round(wind / 1.609344, 1)
            if precip is not None:
                precip = round(precip / 25.4, 2)

        return ToolResult(
            success=True,
            data={
                "latitude": latitude,
                "longitude": longitude,
                "timezone": weather_data.timezone,
                "temperature": temp,
                "feels_like": apparent,
                "humidity": weather_data.relative_humidity,
                "wind_speed": wind,
                "precipitation": precip,
                "unit_system": units,
                "temp_unit": "F" if units.lower() == "imperial" else "C",
                "wind_unit": "mph" if units.lower() == "imperial" else "km/h",
                "precip_unit": "inch" if units.lower() == "imperial" else "mm",
                "weather_code": weather_data.current_weather_code,
                "description": weather_data.current_description,
                "observation_time": weather_data.observation_time
            }
        )

class WeatherForecastInput(BaseModel):
    latitude: float = Field(..., description="Latitude coordinate.")
    longitude: float = Field(..., description="Longitude coordinate.")
    forecast_days: int = Field(default=3, ge=1, le=7, description="Number of days of daily forecast (1-7).")
    units: str = Field(default="metric", description="Unit system: 'metric' (Celsius, km/h) or 'imperial' (Fahrenheit, mph).")

class WeatherForecastTool(BaseTool):
    name: str = "weather_forecast"
    description: str = "Get daily weather forecast (temperature max/min, conditions, rain probability) for given latitude and longitude coordinates."
    input_schema: Any = WeatherForecastInput
    permission_level: str = "safe"
    timeout_seconds: int = 15

    async def execute(self, latitude: float, longitude: float, forecast_days: int = 3, units: str = "metric", **kwargs) -> ToolResult:
        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": "Latitude must be between -90 and 90, and longitude between -180 and 180."}
            )
        if not (1 <= forecast_days <= 7):
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": "Forecast days must be between 1 and 7."}
            )
        weather_data = weather_cache.get_weather(latitude, longitude, forecast_days)
        if not weather_data:
            try:
                provider = OpenMeteoWeatherProvider()
                weather_data = await provider.get_weather(latitude, longitude, forecast_days)
                weather_cache.set_weather(latitude, longitude, forecast_days, result=weather_data)
            except WeatherException as we:
                return ToolResult(success=False, error=we.code, metadata={"error_detail": str(we)})
            except Exception as e:
                return ToolResult(success=False, error="WEATHER_FETCH_FAILED", metadata={"error_detail": str(e)})

        forecast_list = []
        for item in weather_data.daily_forecast[:forecast_days]:
            t_max = item.temperature_max
            t_min = item.temperature_min
            precip_sum = item.precipitation_sum
            if units.lower() == "imperial":
                t_max = round((t_max * 9 / 5) + 32, 1)
                t_min = round((t_min * 9 / 5) + 32, 1)
                if precip_sum is not None:
                    precip_sum = round(precip_sum / 25.4, 2)
            forecast_list.append({
                "date": item.date,
                "temperature_max": t_max,
                "temperature_min": t_min,
                "weather_code": item.weather_code,
                "description": item.description,
                "precipitation_probability": item.precipitation_probability,
                "precipitation_sum": precip_sum
            })

        return ToolResult(
            success=True,
            data={
                "latitude": latitude,
                "longitude": longitude,
                "timezone": weather_data.timezone,
                "unit_system": units,
                "temp_unit": "F" if units.lower() == "imperial" else "C",
                "precip_unit": "inch" if units.lower() == "imperial" else "mm",
                "forecast": forecast_list
            }
        )
