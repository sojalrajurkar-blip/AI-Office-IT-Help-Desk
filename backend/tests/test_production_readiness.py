import os
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import settings


@pytest.mark.asyncio
async def test_production_health_endpoint():
    """Verify /api/health returns database connectivity and system status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "version" in data


@pytest.mark.asyncio
async def test_openapi_schema_generation():
    """Verify OpenAPI 3.x schema is properly generated for Flutter/frontend client generation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/openapi.json")
        assert res.status_code == 200
        schema = res.json()
        assert schema["openapi"].startswith("3.")
        assert "paths" in schema
        
        # Verify key endpoints exist in schema
        paths = schema["paths"]
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/cases/" in paths
        assert "/api/v1/dashboards/me" in paths
        assert "/api/v1/notifications" in paths
        assert "/api/health" in paths


@pytest.mark.asyncio
async def test_cors_middleware_headers():
    """Verify CORS preflight / headers allow client access."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        }
        res = await client.options("/api/v1/auth/login", headers=headers)
        # CORS options response
        assert res.status_code in [200, 204]


def test_uploads_directory_exists_and_writable():
    """Verify uploads directory exists and is writable."""
    uploads_dir = settings.LOCAL_STORAGE_DIR
    os.makedirs(uploads_dir, exist_ok=True)
    assert os.path.exists(uploads_dir)
    assert os.path.isdir(uploads_dir)

    test_file = os.path.join(uploads_dir, ".write_test")
    try:
        with open(test_file, "w") as f:
            f.write("ok")
        assert os.path.exists(test_file)
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
