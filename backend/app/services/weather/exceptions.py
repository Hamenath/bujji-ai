from app.core.exceptions import AppException

class WeatherException(AppException):
    def __init__(self, message: str, code: str = "WEATHER_ERROR", status_code: int = 400):
        super().__init__(message=message, code=code, status_code=status_code)

class WeatherProviderUnavailableError(WeatherException):
    def __init__(self, message: str):
        super().__init__(message=message, code="WEATHER_PROVIDER_UNAVAILABLE", status_code=503)

class GeocodingFailedError(WeatherException):
    def __init__(self, message: str):
        super().__init__(message=message, code="GEOCODING_FAILED", status_code=400)

class LocationNotFoundError(WeatherException):
    def __init__(self, message: str):
        super().__init__(message=message, code="LOCATION_NOT_FOUND", status_code=404)
