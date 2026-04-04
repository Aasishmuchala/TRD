"""Tests for core API routes (simulate, presets, history, auth)."""

import pytest
from app.api.schemas import MarketInput


@pytest.mark.asyncio
async def test_simulate_with_valid_market_input(test_client):
    """Test POST /api/simulate with valid market input returns simulation result."""
    market_data = {
        "nifty_spot": 24000.0,
        "india_vix": 16.5,
        "fii_flow_5d": 100.0,
        "dii_flow_5d": -50.0,
        "usd_inr": 83.2,
        "dxy": 104.5,
        "pcr_index": 1.1,
        "max_pain": 24000.0,
        "dte": 5,
        "context": "normal",
    }

    payload = {
        "market_input": market_data
    }

    response = await test_client.post("/api/simulate", json=payload)

    assert response.status_code == 200
    data = response.json()

    # Check core simulation result fields
    assert "simulation_id" in data
    assert "timestamp" in data
    assert "market_input" in data
    assert "agents_output" in data
    assert "aggregator_result" in data
    assert "execution_time_ms" in data
    assert "model_used" in data

    # Check aggregator result has required fields
    agg = data["aggregator_result"]
    assert "final_direction" in agg
    assert "final_conviction" in agg
    assert "consensus_score" in agg
    assert "conflict_level" in agg

    # Verify agent responses exist
    assert isinstance(data["agents_output"], dict)
    assert len(data["agents_output"]) > 0


@pytest.mark.asyncio
async def test_simulate_with_invalid_data(test_client):
    """Test POST /api/simulate with invalid data returns 422."""
    # Missing required fields
    payload = {
        "market_input": {
            # nifty_spot is required but missing — triggers Pydantic 422
            "india_vix": 18.0,
        }
    }

    response = await test_client.post("/api/simulate", json=payload)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_simulate_with_flat_fields(test_client):
    """Test POST /api/simulate with flat market fields (backwards compatibility)."""
    payload = {
        "nifty_spot": 24000.0,
        "india_vix": 16.5,
        "fii_flow_5d": 100.0,
        "dii_flow_5d": -50.0,
        "usd_inr": 83.2,
        "dxy": 104.5,
        "pcr_index": 1.1,
        "max_pain": 24000.0,
        "dte": 5,
        "context": "normal",
    }

    response = await test_client.post("/api/simulate", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "simulation_id" in data
    assert "aggregator_result" in data


@pytest.mark.asyncio
async def test_get_presets(test_client):
    """Test GET /api/presets returns list of scenarios."""
    response = await test_client.get("/api/presets")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    if len(data) > 0:
        # Check structure of preset
        preset = data[0]
        assert "scenario_id" in preset
        assert "name" in preset
        assert "description" in preset
        assert "expected_direction" in preset


@pytest.mark.asyncio
async def test_get_history(test_client):
    """Test GET /api/history returns list of simulations."""
    response = await test_client.get("/api/history?limit=10&offset=0")

    assert response.status_code == 200
    data = response.json()

    # Check pagination fields
    assert "total_count" in data
    assert "page" in data
    assert "page_size" in data
    assert "items" in data

    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_auth_login_initiates_device_flow(test_client):
    """Test POST /api/auth/login initiates device flow."""
    response = await test_client.post("/api/auth/login")

    assert response.status_code == 200
    data = response.json()

    # Check device flow response fields
    assert "status" in data
    assert "user_code" in data
    assert "verification_uri" in data
    assert "expires_in" in data
    assert "interval" in data
    assert "provider" in data


@pytest.mark.asyncio
async def test_auth_status(test_client):
    """Test GET /api/auth/status returns auth status."""
    response = await test_client.get("/api/auth/status")

    assert response.status_code == 200
    data = response.json()

    # Check status fields
    assert "authenticated" in data
    assert "provider" in data
    assert "mock_mode" in data

    # In test mode with MOCK_MODE=True, should indicate that
    assert isinstance(data["mock_mode"], bool)


@pytest.mark.asyncio
async def test_simulate_with_scenario_id(test_client):
    """Test POST /api/simulate with scenario_id loads preset."""
    # First get available presets
    presets_response = await test_client.get("/api/presets")
    assert presets_response.status_code == 200
    presets = presets_response.json()

    if len(presets) > 0:
        scenario_id = presets[0]["scenario_id"]

        # Now simulate with that scenario
        payload = {"scenario_id": scenario_id}
        response = await test_client.post("/api/simulate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "simulation_id" in data
        assert "aggregator_result" in data


@pytest.mark.asyncio
async def test_simulate_with_invalid_scenario(test_client):
    """Test POST /api/simulate with invalid scenario_id returns 404."""
    payload = {"scenario_id": "nonexistent_scenario"}
    response = await test_client.post("/api/simulate", json=payload)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Phase 08-02: signal_score in simulate response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simulate_response_contains_signal_score(test_client):
    """POST /api/simulate response includes a top-level signal_score object."""
    market_data = {
        "nifty_spot": 24000.0,
        "india_vix": 16.5,
        "fii_flow_5d": 100.0,
        "dii_flow_5d": -50.0,
        "usd_inr": 83.2,
        "dxy": 104.5,
        "pcr_index": 1.1,
        "max_pain": 24000.0,
        "dte": 5,
        "context": "normal",
    }
    payload = {"market_input": market_data}

    response = await test_client.post("/api/simulate", json=payload)

    assert response.status_code == 200
    data = response.json()

    # signal_score must be present in the response
    assert "signal_score" in data, "response missing 'signal_score' key"

    ss = data["signal_score"]
    # Required sub-keys
    assert "score" in ss
    assert "tier" in ss
    assert "direction" in ss
    assert "contributing_factors" in ss
    assert "suggested_instrument" in ss


@pytest.mark.asyncio
async def test_simulate_signal_score_tier_is_valid(test_client):
    """POST /api/simulate signal_score.tier is one of 'strong', 'moderate', 'skip'."""
    market_data = {
        "nifty_spot": 24000.0,
        "india_vix": 16.5,
        "fii_flow_5d": 100.0,
        "dii_flow_5d": -50.0,
        "usd_inr": 83.2,
        "dxy": 104.5,
        "pcr_index": 1.1,
        "max_pain": 24000.0,
        "dte": 5,
        "context": "normal",
    }
    payload = {"market_input": market_data}

    response = await test_client.post("/api/simulate", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert "signal_score" in data
    tier = data["signal_score"]["tier"]
    assert tier in {"strong", "moderate", "skip"}, f"Unexpected tier: {tier!r}"
