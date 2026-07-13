from abc import ABC, abstractmethod
from app.services.weather.schemas import WeatherData

class BaseWeatherProvider(ABC):
    """
    Abstract base class for Weather Providers.
    Ensures provider-independent abstractions.
    """

    @abstractmethod
    async def get_weather(self, latitude: float, longitude: float, forecast_days: int) -> WeatherData:
        """
        Retrieves weather and daily forecast data for the given coordinates.
        """
        pass
