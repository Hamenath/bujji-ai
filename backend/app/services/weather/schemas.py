from pydantic import BaseModel, Field
from typing import List, Optional

WMO_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

def get_wmo_description(code: int) -> str:
    """Helper to translate WMO code to human-readable description."""
    return WMO_CODE_MAP.get(code, "Unknown weather condition")

class GeocodingResult(BaseModel):
    name: str = Field(..., description="Name of the location resolved")
    latitude: float = Field(..., description="Latitude of the location")
    longitude: float = Field(..., description="Longitude of the location")
    timezone: str = Field(..., description="IANA timezone name (e.g. America/New_York)")
    country: Optional[str] = Field(default=None, description="Country of the location")
    admin1: Optional[str] = Field(default=None, description="State/Province/Region of the location")

class DailyForecastItem(BaseModel):
    date: str = Field(..., description="Forecast date (YYYY-MM-DD)")
    temperature_max: float = Field(..., description="Maximum temperature")
    temperature_min: float = Field(..., description="Minimum temperature")
    weather_code: int = Field(..., description="WMO weather interpretation code")
    description: str = Field(..., description="Text description of the weather condition")

class WeatherData(BaseModel):
    latitude: float
    longitude: float
    timezone: str
    location_name: str
    current_temp: float = Field(..., description="Current temperature")
    current_weather_code: int = Field(..., description="Current WMO weather interpretation code")
    current_description: str = Field(..., description="Text description of the current weather")
    daily_forecast: List[DailyForecastItem] = Field(default_factory=list)
