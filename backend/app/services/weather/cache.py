import time
import threading
from typing import Dict, Any, Tuple, Optional
from app.services.weather.schemas import GeocodingResult, WeatherData

class WeatherCache:
    """
    In-memory thread-safe cache for geocoding and weather queries.
    Provides long-term caching for static geocoding coordinates and short-term caching for forecasts.
    """

    def __init__(self):
        self._geo_cache: Dict[str, Tuple[GeocodingResult, float]] = {}
        self._weather_cache: Dict[str, Tuple[WeatherData, float]] = {}
        self._lock = threading.Lock()

    def get_geocoding(self, name: str) -> Optional[GeocodingResult]:
        key = name.strip().lower()
        with self._lock:
            if key in self._geo_cache:
                result, expiry = self._geo_cache[key]
                if time.time() < expiry:
                    return result
                else:
                    del self._geo_cache[key]
        return None

    def set_geocoding(self, name: str, result: GeocodingResult, ttl: float = 7 * 24 * 3600) -> None:
        key = name.strip().lower()
        expiry = time.time() + ttl
        with self._lock:
            self._geo_cache[key] = (result, expiry)

    def get_weather(self, lat: float, lon: float, forecast_days: int) -> Optional[WeatherData]:
        # round lat/lon to 3 decimal places to cluster close queries (approx. 110 meters)
        key = f"{round(lat, 3)}:{round(lon, 3)}:{forecast_days}"
        with self._lock:
            if key in self._weather_cache:
                result, expiry = self._weather_cache[key]
                if time.time() < expiry:
                    return result
                else:
                    del self._weather_cache[key]
        return None

    def set_weather(self, lat: float, lon: float, forecast_days: int, result: WeatherData, ttl: float = 600) -> None:
        key = f"{round(lat, 3)}:{round(lon, 3)}:{forecast_days}"
        expiry = time.time() + ttl
        with self._lock:
            self._weather_cache[key] = (result, expiry)

    def clear(self) -> None:
        with self._lock:
            self._geo_cache.clear()
            self._weather_cache.clear()

weather_cache = WeatherCache()
