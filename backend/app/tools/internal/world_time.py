from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult
from app.services.weather.geocoding import geocoding_service
from app.services.weather.open_meteo import OpenMeteoWeatherProvider
from app.services.weather.cache import weather_cache
from app.services.weather.exceptions import WeatherException

class WorldTimeInput(BaseModel):
    timezone_or_city: Optional[str] = Field(
        default=None,
        description="The timezone identifier (e.g. 'Europe/London', 'America/New_York') or city name (e.g. 'Tokyo', 'London') or coordinates string 'lat,lon'."
    )
    latitude: Optional[float] = Field(default=None, description="Direct latitude coordinate.")
    longitude: Optional[float] = Field(default=None, description="Direct longitude coordinate.")

def parse_coordinates(s: str) -> Optional[tuple[float, float]]:
    parts = s.split(",")
    if len(parts) == 2:
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                return lat, lon
        except ValueError:
            pass
    return None

class WorldTimeTool(BaseTool):
    name: str = "world_time"
    description: str = (
        "Get the current local date, time, and timezone offset for a specified city, timezone name, or coordinate location."
    )
    input_schema: Any = WorldTimeInput
    permission_level: str = "safe"
    timeout_seconds: int = 10

    async def execute(
        self,
        timezone_or_city: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        **kwargs
    ) -> ToolResult:
        resolved_tz_name = None
        location_label = None
        tz = None

        resolved_lat = latitude
        resolved_lon = longitude

        if resolved_lat is not None and resolved_lon is not None:
            if not (-90.0 <= resolved_lat <= 90.0) or not (-180.0 <= resolved_lon <= 180.0):
                return ToolResult(
                    success=False,
                    error="INVALID_ARGUMENTS",
                    metadata={"error_detail": "Latitude must be between -90 and 90, and longitude between -180 and 180."}
                )
            location_label = f"{resolved_lat},{resolved_lon}"
        elif timezone_or_city and timezone_or_city.strip():
            query_str = timezone_or_city.strip()
            # Clean spaces and check if it is direct timezone string
            clean_tz = query_str.replace(" ", "")
            try:
                tz = ZoneInfo(clean_tz)
                resolved_tz_name = clean_tz
                location_label = clean_tz
            except Exception:
                # Check if it is a coordinate string
                coords = parse_coordinates(query_str)
                if coords:
                    resolved_lat, resolved_lon = coords
                    location_label = f"{resolved_lat},{resolved_lon}"
                else:
                    # Treat as a city name
                    pass
        else:
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": "Either 'timezone_or_city' or both 'latitude' and 'longitude' must be provided."}
            )

        if resolved_lat is not None and resolved_lon is not None:
            # Check weather cache first if coordinates are already cached
            weather_data = weather_cache.get_weather(resolved_lat, resolved_lon, forecast_days=1)
            if not weather_data:
                try:
                    provider = OpenMeteoWeatherProvider()
                    weather_data = await provider.get_weather(resolved_lat, resolved_lon, forecast_days=1)
                    weather_cache.set_weather(resolved_lat, resolved_lon, forecast_days=1, result=weather_data)
                except Exception as e:
                    return ToolResult(
                        success=False,
                        error="WEATHER_FETCH_FAILED",
                        metadata={"error_detail": f"Failed to retrieve timezone for coordinates: {e}"}
                    )
            try:
                resolved_tz_name = weather_data.timezone
                tz = ZoneInfo(resolved_tz_name)
            except Exception:
                tz = ZoneInfo("UTC")
                resolved_tz_name = "UTC"
                location_label = f"{location_label} (Fallback UTC)"
        elif tz is None:
            assert timezone_or_city is not None
            resolved_tz_name = timezone_or_city.strip()
            geo_res = weather_cache.get_geocoding(resolved_tz_name)
            if not geo_res:
                try:
                    geo_res = await geocoding_service.resolve(resolved_tz_name)
                    weather_cache.set_geocoding(resolved_tz_name, geo_res)
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
            
            try:
                tz = ZoneInfo(geo_res.timezone)
                resolved_tz_name = geo_res.timezone
                location_label = f"{geo_res.name}, {geo_res.country or ''}".strip(", ")
            except Exception:
                tz = ZoneInfo("UTC")
                resolved_tz_name = "UTC"
                location_label = f"{geo_res.name} (Fallback UTC)"

        # 3. Retrieve local time details
        now = datetime.now(tz)
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        offset = now.strftime("%z")
        
        # Format offset nicely: e.g. +0530 -> UTC+05:30
        if len(offset) == 5:
            formatted_offset = f"UTC{offset[:3]}:{offset[3:]}"
        else:
            formatted_offset = "UTC+00:00"

        return ToolResult(
            success=True,
            data={
                "location": location_label,
                "timezone": resolved_tz_name,
                "current_time": time_str,
                "utc_offset": formatted_offset,
                "iso_datetime": now.isoformat()
            }
        )
