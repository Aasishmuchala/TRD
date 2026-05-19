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

    # The health payload currently exposes status/timestamp/version/database.
    # Optional runtime fields (model, mock_mode, llm_provider, learning_enabled)
    # are added by deployment wiring and may not be present in unit tests; we
    # only assert their types when present.
    for key in ("model", "mock_mode", "llm_provider", "learning_enabled"):
        if key in data:
            if key in ("mock_mode", "learning_enabled"):
                assert isinstance(data[key], bool)
            else:
                assert isinstance(data[key], str)
