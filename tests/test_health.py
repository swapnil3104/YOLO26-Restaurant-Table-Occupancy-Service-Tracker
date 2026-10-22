"""Tests for health and metadata endpoints."""

from fastapi.testclient import TestClient

from smartserve.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns system metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "version" in data
    assert data["app"] == "SmartServe AI"


def test_health_endpoint():
    """Verify health endpoint returns status without leaking sensitive details."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data
    assert "services" in data
    # Security assertion: ensure no database connection strings or secret keys are returned
    content_str = response.text.lower()
    assert "secret" not in content_str
    assert "password" not in content_str
    assert "key" not in content_str or "secret_key" not in content_str

