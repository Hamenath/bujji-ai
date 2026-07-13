from app.core.exceptions import AppException
from fastapi import status

class WebException(AppException):
    """Base exception for all web/fetch-related issues."""
    def __init__(self, message: str, code: str = "WEB_ERROR", status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message=message, code=code, status_code=status_code)

class InvalidURLError(WebException):
    def __init__(self, message: str, code: str = "INVALID_URL"):
        super().__init__(message, code=code)

class SSRFBlockedError(WebException):
    def __init__(self, message: str, code: str = "SSRF_BLOCKED"):
        super().__init__(message, code=code, status_code=status.HTTP_403_FORBIDDEN)

class TooManyRedirectsError(WebException):
    def __init__(self, message: str, code: str = "TOO_MANY_REDIRECTS"):
        super().__init__(message, code=code)

class RedirectLoopError(WebException):
    def __init__(self, message: str, code: str = "REDIRECT_LOOP"):
        super().__init__(message, code=code)

class FetchTimeoutError(WebException):
    def __init__(self, message: str, code: str = "FETCH_TIMEOUT"):
        super().__init__(message, code=code, status_code=status.HTTP_504_GATEWAY_TIMEOUT)

class ResponseTooLargeError(WebException):
    def __init__(self, message: str, code: str = "RESPONSE_TOO_LARGE"):
        super().__init__(message, code=code)

class UnsupportedContentTypeError(WebException):
    def __init__(self, message: str, code: str = "UNSUPPORTED_CONTENT_TYPE"):
        super().__init__(message, code=code)

class ContentExtractionError(WebException):
    def __init__(self, message: str, code: str = "CONTENT_EXTRACTION_FAILED"):
        super().__init__(message, code=code)
