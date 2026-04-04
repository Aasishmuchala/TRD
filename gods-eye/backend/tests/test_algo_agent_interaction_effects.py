"""Tests for AlgoQuantAgent interaction_effects — verifies BACK-04 compliance."""

import pytest
import pytest_asyncio
from app.api.schemas import MarketInput
from app.agents.algo_agent import AlgoQuantAgent


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
async def test_interaction_effects_not_empty():
    """AlgoQuantAgent must return non-empty amplifies and dampens lists."""
    agent = AlgoQuantAgent()
    md = make_market_input()
    resp = await agent.analyze(md)
    effects = resp.interaction_effects
    assert len(effects.get("amplifies", [])) >= 2, (
        f"amplifies must have >= 2 items, got: {effects.get('amplifies')}"
    )
    assert len(effects.get("dampens", [])) >= 1, (
        f"dampens must have >= 1 item, got: {effects.get('dampens')}"
    )


@pytest.mark.asyncio
async def test_high_vix_includes_volatility_regime_signal():
    """High VIX (india_vix >= 20) must include 'Volatility regime signals' in amplifies."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=25.0)
    resp = await agent.analyze(md)
    effects = resp.interaction_effects
    assert "Volatility regime signals" in effects.get("amplifies", []), (
        f"High VIX should add 'Volatility regime signals', got: {effects.get('amplifies')}"
    )


@pytest.mark.asyncio
async def test_low_vix_includes_momentum_strategies():
    """Low VIX (india_vix < 14) must include 'Momentum strategies' in amplifies."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=12.0)
    resp = await agent.analyze(md)
    effects = resp.interaction_effects
    assert "Momentum strategies" in effects.get("amplifies", []), (
        f"Low VIX should add 'Momentum strategies', got: {effects.get('amplifies')}"
    )


@pytest.mark.asyncio
async def test_overbought_rsi_adds_divergence_signal():
    """RSI > 70 must add 'Overbought divergence signals' to amplifies."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=18.0, rsi_14=75.0)
    resp = await agent.analyze(md)
    effects = resp.interaction_effects
    assert "Overbought divergence signals" in effects.get("amplifies", []), (
        f"RSI=75 should add 'Overbought divergence signals', got: {effects.get('amplifies')}"
    )


@pytest.mark.asyncio
async def test_oversold_rsi_adds_reversal_signal():
    """RSI < 30 must add 'Oversold reversal signals' to amplifies."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=18.0, rsi_14=25.0)
    resp = await agent.analyze(md)
    effects = resp.interaction_effects
    assert "Oversold reversal signals" in effects.get("amplifies", []), (
        f"RSI=25 should add 'Oversold reversal signals', got: {effects.get('amplifies')}"
    )


@pytest.mark.asyncio
async def test_elevated_vix_adds_range_bound_signal():
    """Elevated VIX (14 <= vix < 20) must include 'Range-bound mean-reversion signals'."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=18.0)
    resp = await agent.analyze(md)
    effects = resp.interaction_effects
    assert "Range-bound mean-reversion signals" in effects.get("amplifies", []), (
        f"Elevated VIX should add 'Range-bound mean-reversion signals', got: {effects.get('amplifies')}"
    )


@pytest.mark.asyncio
async def test_always_has_base_signals():
    """amplifies always includes base items regardless of market conditions."""
    agent = AlgoQuantAgent()
    md = make_market_input(india_vix=18.0)
    resp = await agent.analyze(md)
    effects = resp.interaction_effects
    assert "Cross-agent consensus signals" in effects.get("amplifies", []), (
        f"Base 'Cross-agent consensus signals' always required, got: {effects.get('amplifies')}"
    )
    assert "Technical confirmation" in effects.get("amplifies", []), (
        f"Base 'Technical confirmation' always required, got: {effects.get('amplifies')}"
    )
    assert "Noise and whipsaws" in effects.get("dampens", []), (
        f"Base 'Noise and whipsaws' always required in dampens, got: {effects.get('dampens')}"
    )
