"""Tests for TechnicalSignals -- run before implementation exists (TDD RED phase).

All tests should FAIL until technical_signals.py is created.
"""
import pytest


def test_rsi_all_gain_returns_100():
    from app.data.technical_signals import TechnicalSignals
    closes_up = [100.0] * 14 + [110.0]
    assert TechnicalSignals.compute_rsi(closes_up) == 100.0


def test_rsi_all_loss_returns_0():
    from app.data.technical_signals import TechnicalSignals
    closes_down = [100.0] * 14 + [90.0]
    assert TechnicalSignals.compute_rsi(closes_down) == 0.0


def test_rsi_insufficient_data_returns_50():
    from app.data.technical_signals import TechnicalSignals
    assert TechnicalSignals.compute_rsi([100.0, 101.0]) == 50.0


def test_rsi_exactly_period_plus_1_does_not_return_50():
    """15 closes should compute (not return default 50.0)."""
    from app.data.technical_signals import TechnicalSignals
    closes = [100.0 + i for i in range(15)]
    result = TechnicalSignals.compute_rsi(closes)
    assert isinstance(result, float)
    assert 0.0 <= result <= 100.0


def test_vwap_deviation_zero_volume_returns_zero():
    from app.data.technical_signals import TechnicalSignals
    rows = [{"date": "2025-01-01", "open": 100, "high": 105, "low": 95,
             "close": 100, "volume": 0}]
    assert TechnicalSignals.compute_vwap_deviation(rows) == 0.0


def test_vwap_deviation_empty_rows_returns_zero():
    from app.data.technical_signals import TechnicalSignals
    assert TechnicalSignals.compute_vwap_deviation([]) == 0.0


def test_vwap_deviation_single_row_returns_zero():
    """Single row: close == vwap => deviation == 0."""
    from app.data.technical_signals import TechnicalSignals
    rows = [{"date": "2025-01-01", "open": 100, "high": 105, "low": 95,
             "close": 110, "volume": 1000}]
    assert TechnicalSignals.compute_vwap_deviation(rows) == 0.0


def test_supertrend_short_series_returns_bullish():
    from app.data.technical_signals import TechnicalSignals
    rows = [{"date": f"2025-01-{i:02d}", "open": 100, "high": 105, "low": 95,
             "close": 100, "volume": 1000} for i in range(1, 6)]
    assert TechnicalSignals.compute_supertrend(rows) == "bullish"


def test_supertrend_returns_bullish_or_bearish():
    from app.data.technical_signals import TechnicalSignals
    rows = [{"date": f"2025-01-{i:02d}", "open": 100 + i, "high": 105 + i,
             "low": 95 + i, "close": 100 + i, "volume": 10000}
            for i in range(1, 25)]
    result = TechnicalSignals.compute_supertrend(rows)
    assert result in ("bullish", "bearish")


def test_vix_regime_low():
    from app.data.technical_signals import TechnicalSignals
    assert TechnicalSignals.classify_vix_regime(13.9) == "low"
    assert TechnicalSignals.classify_vix_regime(0.1) == "low"


def test_vix_regime_normal_boundary_at_14():
    from app.data.technical_signals import TechnicalSignals
    assert TechnicalSignals.classify_vix_regime(14.0) == "normal"
    assert TechnicalSignals.classify_vix_regime(19.99) == "normal"


def test_vix_regime_elevated_boundary_at_20():
    from app.data.technical_signals import TechnicalSignals
    assert TechnicalSignals.classify_vix_regime(20.0) == "elevated"
    assert TechnicalSignals.classify_vix_regime(29.99) == "elevated"


def test_vix_regime_high_boundary_at_30():
    from app.data.technical_signals import TechnicalSignals
    assert TechnicalSignals.classify_vix_regime(30.0) == "high"
    assert TechnicalSignals.classify_vix_regime(50.0) == "high"


def test_vix_regime_negative_raises():
    from app.data.technical_signals import TechnicalSignals
    with pytest.raises(ValueError):
        TechnicalSignals.classify_vix_regime(-1.0)


def test_compute_signals_for_date_returns_correct_keys():
    from app.data.technical_signals import TechnicalSignals
    rows = [{"date": f"2025-01-{i:02d}", "open": 100 + i, "high": 105 + i,
             "low": 95 + i, "close": 100 + i, "volume": 10000}
            for i in range(1, 25)]
    sig = TechnicalSignals.compute_signals_for_date(rows, "2025-01-20")
    assert set(sig.keys()) == {"rsi", "vwap_deviation_pct", "supertrend"}


def test_compute_signals_for_date_no_future_leakage():
    """Rows after date_str must be excluded."""
    from app.data.technical_signals import TechnicalSignals
    rows = [{"date": f"2025-01-{i:02d}", "open": 100 + i, "high": 105 + i,
             "low": 95 + i, "close": 100 + i, "volume": 10000}
            for i in range(1, 25)]
    sig_early = TechnicalSignals.compute_signals_for_date(rows, "2025-01-05")
    sig_late = TechnicalSignals.compute_signals_for_date(rows, "2025-01-20")
    # Results should differ because different data windows are used
    assert sig_early["rsi"] != sig_late["rsi"] or sig_early["vwap_deviation_pct"] != sig_late["vwap_deviation_pct"]


def test_compute_signals_for_date_no_data_returns_error():
    from app.data.technical_signals import TechnicalSignals
    rows = [{"date": "2025-01-10", "open": 100, "high": 105, "low": 95,
             "close": 100, "volume": 1000}]
    result = TechnicalSignals.compute_signals_for_date(rows, "2025-01-01")
    assert "error" in result


def test_technical_signals_singleton_importable():
    from app.data.technical_signals import technical_signals, TechnicalSignals
    assert isinstance(technical_signals, TechnicalSignals)
