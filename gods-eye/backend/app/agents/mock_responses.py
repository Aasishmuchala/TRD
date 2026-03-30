"""Mock response generator for LLM agents when no API key is available."""

import random
import hashlib
from typing import Dict, Optional, List
from app.api.schemas import AgentResponse, MarketInput


class MockResponseGenerator:
    """Generates deterministic, scenario-aware mock responses for each agent."""

    # Scenario-specific response templates per agent
    AGENT_TEMPLATES = {
        "FII": {
            "RBI_DOVISH": {"direction": "BUY", "conviction": 68, "reasoning": "RBI dovish stance supports risk-on. Lower rates improve carry trade attractiveness for FII flows into Indian equities. USD/INR stability expected.", "triggers": ["RBI rate cut signal", "Carry trade opportunity", "EM rotation into India"]},
            "FII_OUTFLOW": {"direction": "STRONG_SELL", "conviction": 88, "reasoning": "Massive FII outflows accelerating. DXY strength and US rate trajectory make EM allocations unattractive. Reducing India overweight.", "triggers": ["DXY above 108", "EM fund redemptions", "MSCI rebalancing risk"]},
            "BUDGET_POSITIVE": {"direction": "BUY", "conviction": 72, "reasoning": "Pro-growth budget improves India's macro story. No new taxes on FIIs, capex push supports earnings. Maintaining India allocation.", "triggers": ["No LTCG hike", "Capex multiplier", "Fiscal discipline maintained"]},
            "BUDGET_NEGATIVE": {"direction": "SELL", "conviction": 75, "reasoning": "Corporate tax hike reduces post-tax returns. Fiscal expansion concerns raise inflation risk. Trimming India allocation.", "triggers": ["Corporate tax increase", "Fiscal slippage risk", "HNI surcharge impact on flows"]},
            "EXPIRY_WEEK": {"direction": "HOLD", "conviction": 45, "reasoning": "Expiry-week volatility is noise for institutional positioning. Maintaining current allocation pending macro clarity.", "triggers": ["Expiry noise", "Gamma positioning", "Await post-expiry trend"]},
            "GLOBAL_CRISIS": {"direction": "STRONG_SELL", "conviction": 92, "reasoning": "Global risk-off in full force. Exiting EM positions to reduce portfolio VAR. India not immune to contagion despite strong domestic story.", "triggers": ["US bank stress", "EM contagion spreading", "Flight to US Treasuries"]},
            "CORPORATE_SHOCK": {"direction": "SELL", "conviction": 70, "reasoning": "Governance concerns raise India discount risk. FIIs sensitive to corporate transparency issues. Reducing exposure to affected sectors.", "triggers": ["Governance red flag", "India risk premium widening", "Sector rotation out of conglomerates"]},
            "ELECTION_UNCERTAINTY": {"direction": "SELL", "conviction": 65, "reasoning": "Coalition uncertainty increases policy risk premium. FIIs prefer clarity on reform continuity before deploying fresh capital.", "triggers": ["Policy uncertainty", "Coalition dynamics unclear", "Reform continuity at risk"]},
            "normal": {"direction": "HOLD", "conviction": 50, "reasoning": "Stable macro backdrop. India allocation at benchmark weight. Monitoring DXY and FII flow trends for next rebalancing window.", "triggers": ["Benchmark weight", "DXY stable", "Quarterly rebalancing window"]},
        },
        "DII": {
            "RBI_DOVISH": {"direction": "STRONG_BUY", "conviction": 78, "reasoning": "Rate cut supports equity valuations. SIP inflows at record ₹21,000 Cr/month. Deploying into banking and rate-sensitive sectors.", "triggers": ["SIP inflow strength", "Rate cut boosts banks", "Valuation support from lower yields"]},
            "FII_OUTFLOW": {"direction": "BUY", "conviction": 72, "reasoning": "FII selling creates buying opportunity for DIIs. SIP flows provide ammunition. Deploying into quality large-caps at discounted valuations.", "triggers": ["SIP flows absorbing FII selling", "Valuation attractive post-selloff", "Quality at discount"]},
            "BUDGET_POSITIVE": {"direction": "STRONG_BUY", "conviction": 82, "reasoning": "Budget boosts capex and consumption themes. Deploying fresh SIP inflows into infra, defence, and consumer discretionary mandates.", "triggers": ["Capex theme strengthened", "Consumer boost", "SIP deployment into budget beneficiaries"]},
            "BUDGET_NEGATIVE": {"direction": "HOLD", "conviction": 55, "reasoning": "Budget headwinds but SIP flows continue. Maintaining equity allocation at mandate levels. Selective buying on dips.", "triggers": ["SIP flows continue", "Mandate compliance", "Selective accumulation"]},
            "EXPIRY_WEEK": {"direction": "BUY", "conviction": 60, "reasoning": "Using expiry-week volatility to accumulate. SIP deployment continues regardless of short-term noise.", "triggers": ["SIP deployment on dips", "Volatility = opportunity", "Long-term accumulation"]},
            "GLOBAL_CRISIS": {"direction": "BUY", "conviction": 65, "reasoning": "Global crisis creates deep value. India domestic story intact. Deploying SIP inflows aggressively into oversold quality names.", "triggers": ["India decoupling potential", "SIP absorption capacity", "Deep value in large-caps"]},
            "CORPORATE_SHOCK": {"direction": "HOLD", "conviction": 50, "reasoning": "Avoiding affected conglomerate. Redirecting flows to diversified, well-governed companies. SIP mandate unchanged.", "triggers": ["Governance filter applied", "Sector rotation within mandate", "SIP continuity"]},
            "ELECTION_UNCERTAINTY": {"direction": "HOLD", "conviction": 52, "reasoning": "Continuing SIP deployment. Election outcomes don't change India's structural growth story. Maintaining long-term equity allocation.", "triggers": ["Structural growth intact", "SIP auto-deploy", "Long-term mandate"]},
            "normal": {"direction": "BUY", "conviction": 62, "reasoning": "Steady SIP inflows at ₹21,000 Cr/month. Deploying into quality large-caps. Nifty PE reasonable at current levels.", "triggers": ["SIP inflows strong", "PE within range", "Quality accumulation"]},
        },
        "RETAIL_FNO": {
            "RBI_DOVISH": {"direction": "BUY", "conviction": 72, "reasoning": "Rate cut = bullish setup. Buying calls on Nifty. Social sentiment extremely positive. Round number 20,500 likely to be tested.", "triggers": ["Bullish social sentiment", "Call buying surge", "Round level magnet 20,500"]},
            "FII_OUTFLOW": {"direction": "STRONG_SELL", "conviction": 80, "reasoning": "Panic selling across retail. Nifty below key support. Everyone on Telegram saying crash mode. Buying puts aggressively.", "triggers": ["Panic on social media", "Key support broken", "Put buying frenzy"]},
            "BUDGET_POSITIVE": {"direction": "STRONG_BUY", "conviction": 85, "reasoning": "Budget euphoria! Twitter exploding with bullish calls. Buying weekly calls. FOMO is real, everyone is long.", "triggers": ["Budget FOMO", "Social media euphoria", "Weekly call buying"]},
            "BUDGET_NEGATIVE": {"direction": "STRONG_SELL", "conviction": 82, "reasoning": "Budget disaster tweets flooding in. Retail in full panic mode. Buying deep OTM puts. Stop losses getting hit everywhere.", "triggers": ["Budget panic", "Stop loss cascade", "Put premium spiking"]},
            "EXPIRY_WEEK": {"direction": "SELL", "conviction": 68, "reasoning": "Expiry approaching, max pain at 20,000. Nifty trading above max pain — likely to get pulled down. Selling calls, buying puts.", "triggers": ["Max pain magnet", "Gamma squeeze risk", "DTE = 1, high theta"]},
            "GLOBAL_CRISIS": {"direction": "STRONG_SELL", "conviction": 90, "reasoning": "Full panic mode. Gap down opening expected. Buying far OTM puts. VIX spiking, premium through the roof.", "triggers": ["Gap down fear", "VIX explosion", "Telegram groups in panic"]},
            "CORPORATE_SHOCK": {"direction": "SELL", "conviction": 70, "reasoning": "Short-seller report vibes. Retail dumping related stocks. Buying puts on the sector. Social media bearish.", "triggers": ["Short-seller fear", "Sector sell-off", "Social media bearish"]},
            "ELECTION_UNCERTAINTY": {"direction": "SELL", "conviction": 65, "reasoning": "Election uncertainty killing confidence. Retail sitting on hands. Those still in are hedging with puts.", "triggers": ["Uncertainty = bearish retail", "Put hedging", "Low participation"]},
            "normal": {"direction": "HOLD", "conviction": 45, "reasoning": "No clear setup. Waiting for Nifty to break above/below key levels. Selling strangles to collect premium.", "triggers": ["Range-bound market", "Premium selling", "Waiting for breakout"]},
        },
        "PROMOTER": {
            "RBI_DOVISH": {"direction": "HOLD", "conviction": 55, "reasoning": "Rate cut environment is positive. No need to adjust holdings. Promoter stake stable, pledge ratio comfortable.", "triggers": ["Stable control", "No pledge concern", "Positive macro"]},
            "FII_OUTFLOW": {"direction": "BUY", "conviction": 60, "reasoning": "Stock prices falling. Opportunity to increase promoter stake at lower levels. Strengthening control position.", "triggers": ["Opportunistic buying", "Control strengthening", "Attractive valuations"]},
            "BUDGET_POSITIVE": {"direction": "HOLD", "conviction": 50, "reasoning": "Budget positive for business. Maintaining promoter holding. May consider stake sale at higher levels for capex.", "triggers": ["Business positive", "Capex planning", "Hold for now"]},
            "BUDGET_NEGATIVE": {"direction": "BUY", "conviction": 58, "reasoning": "Supporting stock through selective buying. Pledge ratios need protection in falling market.", "triggers": ["Pledge protection", "Support buying", "Control defence"]},
            "EXPIRY_WEEK": {"direction": "HOLD", "conviction": 40, "reasoning": "Expiry dynamics don't affect promoter strategy. Maintaining position as usual.", "triggers": ["No change in strategy", "Long-term holder", "Expiry irrelevant"]},
            "GLOBAL_CRISIS": {"direction": "BUY", "conviction": 65, "reasoning": "Supporting stock price to avoid pledge triggers. Increasing stake at distressed levels to maintain control.", "triggers": ["Pledge risk mitigation", "Control defence", "Floor buying"]},
            "CORPORATE_SHOCK": {"direction": "BUY", "conviction": 70, "reasoning": "Governance scrutiny requires confidence display. Increasing promoter stake to signal faith in company.", "triggers": ["Confidence signaling", "Stake increase", "Governance response"]},
            "ELECTION_UNCERTAINTY": {"direction": "HOLD", "conviction": 45, "reasoning": "Maintaining status quo. Election outcome doesn't affect company fundamentals directly.", "triggers": ["No change needed", "Business as usual", "Policy neutral"]},
            "normal": {"direction": "HOLD", "conviction": 48, "reasoning": "Promoter holding stable. No stake changes planned. Monitoring for opportunistic accumulation on dips.", "triggers": ["Stable holding", "Monitoring mode", "No SEBI action needed"]},
        },
        "RBI": {
            "RBI_DOVISH": {"direction": "BUY", "conviction": 75, "reasoning": "MPC signals accommodative stance. CPI trending down toward 4% target. Room for 25-50bps cut in next review.", "triggers": ["CPI below 5%", "Growth support needed", "Dovish forward guidance"]},
            "FII_OUTFLOW": {"direction": "HOLD", "conviction": 55, "reasoning": "FII outflows creating rupee pressure. RBI intervening in forex to defend INR. Rate path on hold until stability returns.", "triggers": ["Rupee defence", "Forex intervention", "Rate hold pending stability"]},
            "BUDGET_POSITIVE": {"direction": "BUY", "conviction": 65, "reasoning": "Fiscal discipline maintained in budget. Growth-supportive measures don't add inflation pressure. RBI can continue easing.", "triggers": ["Fiscal discipline", "Low inflation risk", "Easing bias maintained"]},
            "BUDGET_NEGATIVE": {"direction": "SELL", "conviction": 60, "reasoning": "Fiscal expansion raises inflation concerns. RBI may need to pause rate cuts. Monitoring government borrowing program closely.", "triggers": ["Fiscal slippage", "Inflation risk from spending", "Borrowing program impact"]},
            "EXPIRY_WEEK": {"direction": "HOLD", "conviction": 40, "reasoning": "Expiry dynamics are market microstructure. RBI policy unchanged. Maintaining current stance.", "triggers": ["No policy change", "Market microstructure", "Status quo"]},
            "GLOBAL_CRISIS": {"direction": "BUY", "conviction": 70, "reasoning": "Global crisis requires accommodative response. RBI ready with rate cuts and liquidity support. Financial stability is priority.", "triggers": ["Emergency rate cut possible", "Liquidity support ready", "Financial stability mandate"]},
            "CORPORATE_SHOCK": {"direction": "HOLD", "conviction": 50, "reasoning": "Corporate governance issue is SEBI domain. RBI monitoring systemic risk. No policy change warranted.", "triggers": ["SEBI jurisdiction", "Systemic risk monitoring", "No RBI action needed"]},
            "ELECTION_UNCERTAINTY": {"direction": "HOLD", "conviction": 48, "reasoning": "RBI independent of political cycle. Policy based on inflation and growth data, not election outcomes.", "triggers": ["Institutional independence", "Data-dependent", "Above politics"]},
            "normal": {"direction": "HOLD", "conviction": 50, "reasoning": "CPI within 2-6% band. Growth stable. Maintaining current repo rate. Next action data-dependent.", "triggers": ["CPI in band", "Neutral stance", "Data-dependent approach"]},
        },
    }

    @staticmethod
    def generate(
        agent_key: str,
        agent_name: str,
        agent_type: str,
        time_horizon: str,
        market_data: MarketInput,
        round_num: int = 1,
        other_agents: Optional[Dict[str, AgentResponse]] = None,
        enriched_context: Optional[str] = None,
    ) -> AgentResponse:
        """Generate a realistic mock response based on scenario context.

        enriched_context is accepted for API compatibility with LLM agents
        but not used in mock mode (responses are deterministic templates).
        """

        context = market_data.context or "normal"
        templates = MockResponseGenerator.AGENT_TEMPLATES.get(agent_key, {})
        template = templates.get(context, templates.get("normal", {
            "direction": "HOLD",
            "conviction": 50,
            "reasoning": "Insufficient data for strong directional call.",
            "triggers": ["Awaiting clarity", "Neutral stance"],
        }))

        # Add variance based on round_num and market data hash
        seed = int(hashlib.md5(f"{agent_key}{context}{round_num}{market_data.nifty_spot}".encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        conviction = template["conviction"] + rng.uniform(-8, 8)
        conviction = max(15, min(95, conviction))

        # Round 2+ adjustments based on other agents
        direction = template["direction"]
        if other_agents and round_num > 1:
            # Count bearish vs bullish agents
            bearish_count = sum(1 for a in other_agents.values() if a.direction in ("SELL", "STRONG_SELL"))
            bullish_count = sum(1 for a in other_agents.values() if a.direction in ("BUY", "STRONG_BUY"))

            # Retail F&O follows the crowd
            if agent_key == "RETAIL_FNO":
                if bearish_count > bullish_count + 1:
                    if direction in ("BUY", "HOLD"):
                        direction = "SELL"
                        conviction *= 0.85
                elif bullish_count > bearish_count + 1:
                    if direction in ("SELL", "HOLD"):
                        direction = "BUY"
                        conviction *= 0.85

            # DII is contrarian — buys when others sell
            elif agent_key == "DII":
                if bearish_count >= 3:
                    conviction = min(conviction * 1.1, 90)

            # FII adjusts conviction based on consensus
            elif agent_key == "FII":
                if bearish_count >= 4:
                    if direction in ("SELL", "STRONG_SELL"):
                        conviction = min(conviction * 1.05, 95)

        # Build interaction effects
        interaction_map = {
            "FII": {"amplifies": ["RBI policy changes", "US rate decisions"], "dampens": ["Retail sentiment noise"]},
            "DII": {"amplifies": ["Budget announcements", "RBI rate cuts"], "dampens": ["Short-term volatility"]},
            "RETAIL_FNO": {"amplifies": ["Volatility spikes", "Expiry dynamics"], "dampens": ["Long-term trends"]},
            "PROMOTER": {"amplifies": ["Long-term holders"], "dampens": ["Short-term volatility"]},
            "RBI": {"amplifies": ["Global risk events", "Rupee weakness"], "dampens": ["Domestic growth concerns"]},
        }

        return AgentResponse(
            agent_name=agent_name,
            agent_type=agent_type,
            direction=direction,
            conviction=round(conviction, 1),
            reasoning=template["reasoning"],
            key_triggers=template["triggers"],
            time_horizon=time_horizon,
            views={
                time_horizon.lower(): {
                    "direction": direction,
                    "conviction": round(conviction, 1),
                }
            },
            interaction_effects=interaction_map.get(agent_key, {"amplifies": [], "dampens": []}),
            internal_consistency=0.85 + rng.uniform(0, 0.15),
            reproducible=True,
            sample_variance=rng.uniform(2, 12),
        )
