"""Tests for the /api/health endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health_check(test_client):
    """Test GET /api/health returns 200 with correct fields."""
    response = await test_client.get("/api/health")

    assert response.status_code == 200
    data = response.json()

    # Check required fields
    assert "status" in data
    assert data["status"] == "healthy"

    assert "timestamp" in data
    assert "model" in data
    assert "mock_mode" in data
    assert "llm_provider" in data
    assert "learning_enabled" in data

    # Verify types
    assert isinstance(data["status"], str)
    assert isinstance(data["timestamp"], str)
    assert isinstance(data["mock_mode"], bool)
    assert isinstance(data["learning_enabled"], bool)
