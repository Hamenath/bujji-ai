from fastapi import status
from unittest.mock import MagicMock
from app.core.config import settings
from app.database.database import get_db
from app.main import app

def test_health_endpoint_healthy(client):
    """Tests the health endpoint under normal healthy operational conditions."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert "version" in data
    assert "environment" in data
    assert "database" in data
    
    assert data["status"] == "healthy"
    assert data["service"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert data["environment"] == settings.APP_ENV
    assert data["database"] == "connected"

def test_health_endpoint_degraded_db(client):
    """Tests the health endpoint response when the database query fails."""
    # Override dependency with a failing database session mock
    def mock_failing_get_db():
        session_mock = MagicMock()
        session_mock.execute.side_effect = Exception("DB connection timeout")
        try:
            yield session_mock
        finally:
            pass

    app.dependency_overrides[get_db] = mock_failing_get_db
    
    try:
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
    finally:
        # Clear override
        app.dependency_overrides.clear()
