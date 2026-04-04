"""Unit tests for VIX regime gate boundary conditions in BacktestEngine.

Tests all 4 boundary values (VIX = 14.0, 16.0, 20.0) and confirms that
>= vs > comparisons produce the expected conviction floors.
"""
import pytest
from unittest.mock import patch


def make_engine():
    """Create a BacktestEngine instance with mocked dependencies."""
    with patch("app.engine.backtest_engine.Orchestrator"), \
         patch("app.engine.backtest_engine.SignalScorer"), \
         patch("app.engine.backtest_engine.StopLossEngine"):
        from app.engine.backtest_engine import BacktestEngine
        engine = BacktestEngine.__new__(BacktestEngine)
        # Set class-level constants explicitly so tests are self-contained
        engine.VIX_EXTREME_THRESHOLD = 20.0
        engine.VIX_HIGH_FLOOR = 78.0
        engine.VIX_ELEVATED_FLOOR = 72.0
        return engine


class TestVIXGateBoundaries:
    def setup_method(self):
        self.engine = make_engine()

    # ------------------------------------------------------------------
    # Passthrough cases
    # ------------------------------------------------------------------

    def test_hold_passes_through_unchanged(self):
        """HOLD signals must never be blocked or modified by VIX gate."""
        dir_, conv = self.engine._apply_vix_event_gate("HOLD", 50.0, 15.0, None, "2024-01-01")
        assert dir_ == "HOLD"
        assert conv == 50.0

    def test_hold_passes_through_at_extreme_vix(self):
        """HOLD should pass even with VIX > 20."""
        dir_, conv = self.engine._apply_vix_event_gate("HOLD", 50.0, 25.0, None, "2024-01-01")
        assert dir_ == "HOLD"
        assert conv == 50.0

    # ------------------------------------------------------------------
    # Pre-event blackout
    # ------------------------------------------------------------------

    def test_pre_event_blackout_forces_hold(self):
        """Any directional signal with pre_event_blackout event → HOLD."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 80.0, 12.0, "pre_event_blackout", "2024-01-01")
        assert dir_ == "HOLD"

    def test_pre_event_blackout_overrides_high_conviction(self):
        """Even 99.9 conviction can't override a pre-event blackout."""
        dir_, _ = self.engine._apply_vix_event_gate("STRONG_BUY", 99.9, 10.0, "pre_event_blackout", "2024-06-03")
        assert dir_ == "HOLD"

    # ------------------------------------------------------------------
    # VIX > 20 extreme threshold
    # ------------------------------------------------------------------

    def test_vix_exactly_20_uses_high_floor_not_extreme(self):
        """VIX=20.0 — gate uses strict > 20.0, so 20.0 falls into VIX_HIGH tier (floor 78).
        Conviction 80.0 >= 78 → trade passes. VIX must be strictly > 20 to block."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 80.0, 20.0, None, "2024-01-01")
        assert dir_ == "BUY"   # 20.0 is NOT extreme; uses VIX_HIGH_FLOOR=78

        # But low conviction at VIX=20 is blocked by the high floor
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 77.9, 20.0, None, "2024-01-01")
        assert dir_ == "HOLD"  # 77.9 < 78 floor

    def test_vix_above_20_blocks_trade(self):
        """VIX=20.1 is definitively in extreme regime."""
        dir_, _ = self.engine._apply_vix_event_gate("SELL", 90.0, 20.1, None, "2024-01-01")
        assert dir_ == "HOLD"

    def test_vix_just_below_20_allows_high_conviction(self):
        """VIX=19.9 falls into VIX_HIGH zone — conviction >= 78 passes."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 78.1, 19.9, None, "2024-01-01")
        assert dir_ == "BUY"

    def test_vix_just_below_20_blocks_low_conviction(self):
        """VIX=19.9, conviction 77.9 (< 78 floor) → HOLD."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 77.9, 19.9, None, "2024-01-01")
        assert dir_ == "HOLD"

    # ------------------------------------------------------------------
    # VIX 16–20 high floor (VIX_HIGH_FLOOR = 78)
    # ------------------------------------------------------------------

    def test_vix_exactly_16_uses_high_floor(self):
        """VIX=16.0 uses VIX_HIGH_FLOOR=78 (>= 16.0 condition)."""
        # Below floor → HOLD
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 77.9, 16.0, None, "2024-01-01")
        assert dir_ == "HOLD"

    def test_vix_exactly_16_passes_at_floor(self):
        """VIX=16.0, conviction exactly 78.0 → passes."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 78.0, 16.0, None, "2024-01-01")
        assert dir_ == "BUY"

    def test_vix_at_18_uses_high_floor(self):
        """Mid-range VIX 18 also enforces VIX_HIGH_FLOOR=78."""
        dir_, _ = self.engine._apply_vix_event_gate("SELL", 77.9, 18.0, None, "2024-01-01")
        assert dir_ == "HOLD"

        dir_, _ = self.engine._apply_vix_event_gate("SELL", 78.5, 18.0, None, "2024-01-01")
        assert dir_ == "SELL"

    # ------------------------------------------------------------------
    # VIX 14–16 elevated floor (VIX_ELEVATED_FLOOR = 72)
    # ------------------------------------------------------------------

    def test_vix_just_below_16_uses_elevated_floor(self):
        """VIX=15.9 falls in elevated zone — floor = 72."""
        # Below floor → HOLD
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 71.9, 15.9, None, "2024-01-01")
        assert dir_ == "HOLD"
        # At/above floor → trade
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 72.1, 15.9, None, "2024-01-01")
        assert dir_ == "BUY"

    def test_vix_exactly_14_uses_elevated_floor(self):
        """VIX=14.0 uses VIX_ELEVATED_FLOOR=72 (>= 14.0 condition)."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 71.9, 14.0, None, "2024-01-01")
        assert dir_ == "HOLD"

        dir_, _ = self.engine._apply_vix_event_gate("BUY", 72.0, 14.0, None, "2024-01-01")
        assert dir_ == "BUY"

    # ------------------------------------------------------------------
    # VIX < 14 normal floor (config.CONVICTION_FLOOR = 65)
    # ------------------------------------------------------------------

    def test_vix_just_below_14_uses_normal_floor(self):
        """VIX=13.9 uses config.CONVICTION_FLOOR (65) — lowest bar."""
        dir_, _ = self.engine._apply_vix_event_gate("BUY", 64.9, 13.9, None, "2024-01-01")
        assert dir_ == "HOLD"  # 64.9 < 65

        dir_, _ = self.engine._apply_vix_event_gate("BUY", 65.1, 13.9, None, "2024-01-01")
        assert dir_ == "BUY"   # 65.1 >= 65

    def test_vix_very_low_uses_normal_floor(self):
        """VIX=10 (calm market) enforces normal floor 65."""
        dir_, _ = self.engine._apply_vix_event_gate("SELL", 65.0, 10.0, None, "2024-01-01")
        assert dir_ == "SELL"
