from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolResult
from app.services.weather.geocoding import geocoding_service
from app.services.weather.cache import weather_cache
from app.services.weather.exceptions import WeatherException

class WorldTimeInput(BaseModel):
    timezone_or_city: str = Field(
        ...,
        description="The timezone identifier (e.g. 'Europe/London', 'America/New_York') or city name (e.g. 'Tokyo', 'London')."
    )

class WorldTimeTool(BaseTool):
    name: str = "world_time"
    description: str = (
        "Get the current local date, time, and timezone offset for a specified city or timezone name."
    )
    input_schema: Any = WorldTimeInput
    permission_level: str = "safe"
    timeout_seconds: int = 10

    async def execute(self, timezone_or_city: str, **kwargs) -> ToolResult:
        if not timezone_or_city.strip():
            return ToolResult(
                success=False,
                error="INVALID_ARGUMENTS",
                metadata={"error_detail": "Timezone or city name query cannot be empty."}
            )

        resolved_tz_name = timezone_or_city.strip()
        location_label = resolved_tz_name
        
        # 1. Try resolving directly as a timezone string
        try:
            # Clean spaces (e.g. "Europe / London" -> "Europe/London")
            clean_tz = resolved_tz_name.replace(" ", "")
            tz = ZoneInfo(clean_tz)
            resolved_tz_name = clean_tz
        except Exception:
            # 2. Treat as a city/place name and geocode
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
