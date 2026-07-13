import logging
from typing import Optional, Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger("app.exceptions")

class AppException(Exception):
    """Base application exception class for user-defined errors."""
    def __init__(
        self,
        message: str,
        code: str = "BAD_REQUEST",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details

class DatabaseException(AppException):
    """Exception raised when a database query or connection fails."""
    def __init__(self, message: str = "Database connection or operation failed.", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )

class EntityNotFoundException(AppException):
    """Exception raised when a requested database entity is not found."""
    def __init__(self, message: str = "Resource not found.", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details
        )

async def app_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Handles custom application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )

async def validation_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Handles FastAPI Pydantic validation errors."""
    # Convert error structure to human-readable details
    errors_list = []
    for err in exc.errors():
        errors_list.append({
            "field": " -> ".join(str(loc) for loc in err.get("loc", [])),
            "msg": err.get("msg", ""),
            "type": err.get("type", "")
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed for request parameters or body.",
                "details": errors_list
            }
        }
    )

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handles any unhandled exception (internal server error)."""
    logger.exception(f"Unhandled internal server error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": None
            }
        }
    )
