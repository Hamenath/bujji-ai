from app.core.exceptions import AppException
from fastapi import status

class SearchException(AppException):
    """Base exception for search failures."""
    def __init__(self, message: str, code: str = "SEARCH_ERROR", status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(message=message, code=code, status_code=status_code)

class SearchProviderUnavailableError(SearchException):
    def __init__(self, message: str = "Search provider is currently unavailable.", code: str = "SEARCH_PROVIDER_UNAVAILABLE"):
        super().__init__(message, code=code, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

class SearchFailedError(SearchException):
    def __init__(self, message: str, code: str = "SEARCH_FAILED"):
        super().__init__(message, code=code)

class SearchTimeoutError(SearchException):
    def __init__(self, message: str = "Search request timed out.", code: str = "SEARCH_TIMEOUT"):
        super().__init__(message, code=code, status_code=status.HTTP_504_GATEWAY_TIMEOUT)
