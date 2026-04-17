"""Preset market scenarios for simulation."""

from app.api.schemas import MarketInput, PresetScenario


class ScenarioGenerator:
    """Generate preset market scenarios."""

    @staticmethod
    def get_all_scenarios() -> list:
        """Return all 8 preset scenarios."""
        return [
            ScenarioGenerator.scenario_rbi_rate_cut(),
            ScenarioGenerator.scenario_fii_exodus(),
            ScenarioGenerator.scenario_budget_bull(),
            ScenarioGenerator.scenario_budget_bear(),
            ScenarioGenerator.scenario_expiry_carnage(),
            ScenarioGenerator.scenario_global_contagion(),
            ScenarioGenerator.scenario_adani_shock(),
            ScenarioGenerator.scenario_election_day(),
        ]

    @staticmethod
    def scenario_rbi_rate_cut() -> PresetScenario:
        """Scenario: RBI announces rate cut."""
        return PresetScenario(
            scenario_id="rbi_rate_cut",
            name="RBI Rate Cut",
            description="RBI announces 25-50 bps rate cut citing lower inflation",
            market_data=MarketInput(
                nifty_spot=20500,
                nifty_open=20400,
                nifty_high=20600,
                nifty_low=20300,
                nifty_close=20500,
                india_vix=12.5,
                fii_flow_5d=150.0,
                dii_flow_5d=200.0,
                usd_inr=82.5,
                dxy=104.2,
                pcr_index=1.3,
                pcr_stock=0.95,
                max_pain=20400,
                dte=8,
                rsi_14=55,
                macd_signal=0.5,
                context="rbi_policy",
                historical_prices=[20200, 20250, 20300, 20350, 20400, 20500],
            ),
            expected_direction="STRONG_BUY",
        )

    @staticmethod
    def scenario_fii_exodus() -> PresetScenario:
        """Scenario: FII mass selling."""
        return PresetScenario(
            scenario_id="fii_exodus",
            name="FII Mass Exodus",
            description="Foreign investors pull $5B+ citing EM rotation and US rate hikes",
            market_data=MarketInput(
                nifty_spot=19200,
                nifty_open=20300,
                nifty_high=20400,
                nifty_low=19100,
                nifty_close=19200,
                india_vix=28.5,
                fii_flow_5d=-500.0,
                dii_flow_5d=100.0,
                usd_inr=84.2,
                dxy=108.5,
                pcr_index=1.8,
                pcr_stock=1.2,
                max_pain=19300,
                dte=12,
                rsi_14=35,
                macd_signal=-1.2,
                context="normal",
                historical_prices=[20200, 20100, 20000, 19800, 19500, 19200],
            ),
            expected_direction="STRONG_SELL",
        )

    @staticmethod
    def scenario_budget_bull() -> PresetScenario:
        """Scenario: Pro-growth budget announcement."""
        return PresetScenario(
            scenario_id="budget_bull",
            name="Budget Bull",
            description="Union Budget announces tax cuts, capex boost, no wealth tax",
            market_data=MarketInput(
                nifty_spot=21200,
                nifty_open=20800,
                nifty_high=21300,
                nifty_low=20700,
                nifty_close=21200,
                india_vix=11.2,
                fii_flow_5d=250.0,
                dii_flow_5d=300.0,
                usd_inr=81.8,
                dxy=103.1,
                pcr_index=0.85,
                pcr_stock=0.78,
                max_pain=21100,
                dte=20,
                rsi_14=62,
                macd_signal=1.5,
                context="budget",
                historical_prices=[20500, 20700, 20900, 21000, 21100, 21200],
            ),
            expected_direction="STRONG_BUY",
        )

    @staticmethod
    def scenario_budget_bear() -> PresetScenario:
        """Scenario: Fiscal shock from budget."""
        return PresetScenario(
            scenario_id="budget_bear",
            name="Budget Bear",
            description="Budget raises corporate tax, wealth tax sparks selloff",
            market_data=MarketInput(
                nifty_spot=19500,
                nifty_open=20300,
                nifty_high=20400,
                nifty_low=19400,
                nifty_close=19500,
                india_vix=24.8,
                fii_flow_5d=-200.0,
                dii_flow_5d=50.0,
                usd_inr=83.5,
                dxy=105.8,
                pcr_index=1.55,
                pcr_stock=1.1,
                max_pain=19600,
                dte=15,
                rsi_14=42,
                macd_signal=-0.8,
                context="budget",
                historical_prices=[20200, 20150, 20100, 19900, 19700, 19500],
            ),
            expected_direction="STRONG_SELL",
        )

    @staticmethod
    def scenario_expiry_carnage() -> PresetScenario:
        """Scenario: Options expiry week gamma crush."""
        return PresetScenario(
            scenario_id="expiry_carnage",
            name="Expiry Carnage",
            description="Weekly expiry drives sharp volatility, gamma squeeze on downside",
            market_data=MarketInput(
                nifty_spot=19850,
                nifty_open=20100,
                nifty_high=20200,
                nifty_low=19700,
                nifty_close=19850,
                india_vix=22.3,
                fii_flow_5d=50.0,
                dii_flow_5d=75.0,
                usd_inr=83.0,
                dxy=104.5,
                pcr_index=0.65,
                pcr_stock=0.72,
                max_pain=20000,
                dte=1,
                rsi_14=48,
                macd_signal=0.2,
                context="expiry",
                historical_prices=[20200, 20150, 20100, 20000, 19950, 19850],
            ),
            expected_direction="SELL",
        )

    @staticmethod
    def scenario_global_contagion() -> PresetScenario:
        """Scenario: Global financial stress spreads to India."""
        return PresetScenario(
            scenario_id="global_contagion",
            name="Global Contagion",
            description="Credit crisis in US/China spreads, EM currencies under pressure",
            market_data=MarketInput(
                nifty_spot=18800,
                nifty_open=20000,
                nifty_high=20100,
                nifty_low=18700,
                nifty_close=18800,
                india_vix=35.2,
                fii_flow_5d=-800.0,
                dii_flow_5d=150.0,
                usd_inr=85.5,
                dxy=110.2,
                pcr_index=2.1,
                pcr_stock=1.4,
                max_pain=19000,
                dte=10,
                rsi_14=25,
                macd_signal=-2.1,
                context="global_crisis",
                historical_prices=[20100, 19800, 19400, 19100, 18900, 18800],
            ),
            expected_direction="STRONG_SELL",
        )

    @staticmethod
    def scenario_adani_shock() -> PresetScenario:
        """Scenario: Corporate governance shock (Adani-style)."""
        return PresetScenario(
            scenario_id="adani_shock",
            name="Adani Shock",
            description="Major conglomerate disclosure sparks sector rotation, liquidity concerns",
            market_data=MarketInput(
                nifty_spot=19400,
                nifty_open=20200,
                nifty_high=20300,
                nifty_low=19300,
                nifty_close=19400,
                india_vix=26.5,
                fii_flow_5d=-150.0,
                dii_flow_5d=50.0,
                usd_inr=83.8,
                dxy=105.2,
                pcr_index=1.42,
                pcr_stock=1.05,
                max_pain=19500,
                dte=18,
                rsi_14=38,
                macd_signal=-0.5,
                context="earnings_season",
                historical_prices=[20300, 20250, 20150, 19900, 19650, 19400],
            ),
            expected_direction="SELL",
        )

    @staticmethod
    def scenario_election_day() -> PresetScenario:
        """Scenario: Election result surprise."""
        return PresetScenario(
            scenario_id="election_day",
            name="Election Day",
            description="Unexpected election result, coalition uncertainty ahead",
            market_data=MarketInput(
                nifty_spot=19750,
                nifty_open=20100,
                nifty_high=20200,
                nifty_low=19600,
                nifty_close=19750,
                india_vix=29.1,
                fii_flow_5d=-100.0,
                dii_flow_5d=80.0,
                usd_inr=83.3,
                dxy=104.9,
                pcr_index=1.68,
                pcr_stock=1.15,
                max_pain=19800,
                dte=12,
                rsi_14=41,
                macd_signal=-0.3,
                context="election",
                historical_prices=[20200, 20100, 20050, 19950, 19850, 19750],
            ),
            expected_direction="SELL",
        )
