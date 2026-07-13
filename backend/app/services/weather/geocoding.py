import httpx
import logging
from typing import Optional
from app.services.weather.schemas import GeocodingResult
from app.services.weather.exceptions import GeocodingFailedError, LocationNotFoundError

logger = logging.getLogger("app.services.weather.geocoding")

class GeocodingService:
    """
    Service to resolve place names/cities into latitude, longitude, and IANA timezone name.
    Uses the keyless Open-Meteo Geocoding API.
    """

    async def resolve(self, name: str) -> GeocodingResult:
        if not name.strip():
            raise GeocodingFailedError("Location name query cannot be empty.")
            
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            "name": name.strip(),
            "count": 1,
            "language": "en",
            "format": "json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    raise GeocodingFailedError(
                        f"Geocoding API returned status code {response.status_code}: {response.text}"
                    )
                data = response.json()
        except httpx.RequestError as e:
            raise GeocodingFailedError(f"HTTP request to geocoding API failed: {e}")
            
        results = data.get("results")
        if not results:
            raise LocationNotFoundError(f"Could not resolve location: '{name}'")
            
        try:
            item = results[0]
            return GeocodingResult(
                name=item["name"],
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                timezone=item.get("timezone", "UTC"),
                country=item.get("country"),
                admin1=item.get("admin1")
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse geocoding result: {e}. Data: {data}")
            raise GeocodingFailedError(f"Failed to parse geocoding API response: {e}")

geocoding_service = GeocodingService()
