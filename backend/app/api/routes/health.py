import logging
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.database.database import get_db
from app.llm.model_router import model_router

router = APIRouter()
logger = logging.getLogger("app.api.routes.health")

@router.get("/health")
async def health_check(response: Response, db: Session = Depends(get_db)):
    """Verifies that the API service is up and running and is connected to the database and Ollama."""
    database_status = "connected"
    ollama_status = "connected"
    app_status = "healthy"
    
    # Check Database connection
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        database_status = "disconnected"
        app_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Check Ollama connection
    try:
        ollama_active = await model_router.active_provider.check_availability()
        if not ollama_active:
            ollama_status = "disconnected"
            # We don't mark the whole app unhealthy if Ollama is down (since it's a separate integration),
            # but we report its disconnected status.
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        ollama_status = "disconnected"
        
    return {
        "status": app_status,
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": database_status,
        "ollama": ollama_status
    }

