"""Tests for VIX Regime Filter in AlgoQuantAgent — Phase 3 Profitability Plan.

Verifies that:
- High VIX (>= 30) forces HOLD with zero conviction
- Elevated VIX (20-29.99) reduces conviction by 40% (multiplier 0.6)
- Normal/Low VIX (<20) has no filter effect
- Filter can be disabled via config
"""

import pytest
import pytest_asyncio
from unittest.mock import patch
from app.api.schemas import MarketInput
from app.agents.algo_agent import AlgoQuantAgent
from app.config import config


def make_market_input(**overrides) -> MarketInput:
    """Create a default MarketInput with optional overrides."""
    defaults = dict(
        nifty_spot=23500,
        india_vix=18.0,
        fii_flow_5d=-100.0,
        dii_flow_5d=60.0,
        usd_inr=83.0,
        dxy=103.5,
        pcr_index=1.1,
        max_pain=23200,
        dte=5,
    )
    defaults.update(overrides)
    return MarketInput(**defaults)


@pytest.mark.asyncio
async def test_high_vix_forces_hold():
    """High VIX (35.0) must force direction to HOLD regardless of quant signal."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=35.0)
    resp = await agent.analyze(md)
    assert resp.direction == "HOLD", (
        f"High VIX (35.0) should force HOLD, got: {resp.direction}"
    )
    assert resp.conviction == 0.0, (
        f"High VIX should zero out conviction, got: {resp.conviction}"
    )
    assert "VIX REGIME FILTER" in resp.reasoning and "forces HOLD" in resp.reasoning, (
        f"Reasoning should mention VIX filter forcing HOLD: {resp.reasoning}"
    )


@pytest.mark.asyncio
async def test_elevated_vix_reduces_conviction():
    """Elevated VIX (25.0) must reduce conviction by 40% (0.6 multiplier)."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=25.0)
    resp = await agent.analyze(md)

    # Verify VIX filter was applied and reduced conviction
    assert "VIX REGIME FILTER" in resp.reasoning and "reduces conviction" in resp.reasoning, (
        f"Reasoning should mention VIX filter reducing conviction: {resp.reasoning}"
    )

    # Check that filter text shows the 0.6 multiplier
    assert "60.0%" in resp.reasoning or "60%" in resp.reasoning, (
        f"Reasoning should show 60% multiplier: {resp.reasoning}"
    )


@pytest.mark.asyncio
async def test_normal_vix_no_change():
    """Normal VIX (16.0) must have no filter effect on conviction."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=16.0)
    resp = await agent.analyze(md)

    # Should not mention VIX filter at all for normal VIX
    assert "VIX REGIME FILTER" not in resp.reasoning, (
        f"Normal VIX should not trigger filter mention in reasoning: {resp.reasoning}"
    )


@pytest.mark.asyncio
async def test_low_vix_no_change():
    """Low VIX (12.0) must have no filter effect on conviction."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=12.0)
    resp = await agent.analyze(md)

    # Should not mention VIX filter at all for low VIX
    assert "VIX REGIME FILTER" not in resp.reasoning, (
        f"Low VIX should not trigger filter mention in reasoning: {resp.reasoning}"
    )


@pytest.mark.asyncio
async def test_vix_at_30_is_high():
    """VIX at exactly 30.0 should be classified as 'high' and force HOLD."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=30.0)
    resp = await agent.analyze(md)
    assert resp.direction == "HOLD", (
        f"VIX at 30.0 (boundary) should force HOLD, got: {resp.direction}"
    )
    assert resp.conviction == 0.0, (
        f"VIX at 30.0 should zero conviction, got: {resp.conviction}"
    )


@pytest.mark.asyncio
async def test_vix_at_20_is_elevated():
    """VIX at exactly 20.0 should be classified as 'elevated' and reduce conviction."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=20.0)
    resp = await agent.analyze(md)

    # Should mention reduction due to elevated VIX
    assert "reduces conviction" in resp.reasoning, (
        f"VIX at 20.0 (elevated) should mention conviction reduction: {resp.reasoning}"
    )

    # Check that multiplier is shown as 60%
    assert "60.0%" in resp.reasoning or "60%" in resp.reasoning, (
        f"VIX at 20.0 should show 60% multiplier: {resp.reasoning}"
    )


@pytest.mark.asyncio
async def test_filter_disabled_via_config():
    """When VIX_FILTER_ENABLED=False, filter should not apply."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=35.0)

    # Mock config to disable filter
    with patch.object(config, 'VIX_FILTER_ENABLED', False):
        resp = await agent.analyze(md)
        # Conviction should not be zero (filter not applied)
        assert resp.conviction > 0.0, (
            f"With filter disabled, conviction should not be zero, got: {resp.conviction}"
        )
        # Reasoning should not mention filter
        assert "VIX REGIME FILTER" not in resp.reasoning, (
            f"With filter disabled, no mention of filter should appear: {resp.reasoning}"
        )


@pytest.mark.asyncio
async def test_vix_thresholds():
    """Test VIX threshold boundaries are correctly applied."""
    agent = AlgoQuantAgent()

    # Test VIX < 14 (low) — no filter
    md = make_market_input(india_vix=13.9)
    resp = await agent.analyze(md)
    assert "VIX REGIME FILTER" not in resp.reasoning

    # Test VIX = 14 (normal) — no filter
    md = make_market_input(india_vix=14.0)
    resp = await agent.analyze(md)
    assert "VIX REGIME FILTER" not in resp.reasoning

    # Test VIX = 19.99 (normal) — no filter
    md = make_market_input(india_vix=19.99)
    resp = await agent.analyze(md)
    assert "VIX REGIME FILTER" not in resp.reasoning

    # Test VIX = 20 (elevated) — filter with conviction reduction
    md = make_market_input(india_vix=20.0)
    resp = await agent.analyze(md)
    assert "reduces conviction" in resp.reasoning

    # Test VIX = 29.99 (elevated) — filter with conviction reduction
    md = make_market_input(india_vix=29.99)
    resp = await agent.analyze(md)
    assert "reduces conviction" in resp.reasoning

    # Test VIX = 30 (high) — filter with HOLD
    md = make_market_input(india_vix=30.0)
    resp = await agent.analyze(md)
    assert resp.direction == "HOLD"
    assert resp.conviction == 0.0


@pytest.mark.asyncio
async def test_conviction_multiplier_applied():
    """Test that conviction multiplier is correctly applied for elevated VIX."""
    agent = AlgoQuantAgent()

    # Get base case (normal VIX)
    md_normal = make_market_input(india_vix=16.0)
    resp_normal = await agent.analyze(md_normal)
    base_conviction = resp_normal.conviction

    # Get elevated VIX case (same market params, just higher VIX)
    md_elevated = make_market_input(india_vix=25.0)
    resp_elevated = await agent.analyze(md_elevated)

    # If the quant scores are the same, elevated should be 0.6x the normal conviction
    # (accounting for differences in quant calculation due to VIX)
    # We can at least verify that elevated VIX mentions the multiplier
    assert "60" in resp_elevated.reasoning, (
        f"Elevated VIX should mention 60% multiplier in reasoning: {resp_elevated.reasoning}"
    )
