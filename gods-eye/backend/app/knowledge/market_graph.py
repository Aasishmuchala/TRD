"""Indian market knowledge graph — sector correlations and causal chains.

Adapted from MiroFish graph_builder pattern. Instead of dynamic graph construction,
we encode the structural relationships that drive Indian market dynamics as a static
knowledge base. Agents receive relevant relationship context for their archetype.

Key insight: A knowledge graph of "banking sector correlates with NBFC sector" is
more useful to an LLM agent than raw correlation numbers, because the LLM can
reason about *why* the correlation exists and when it might break.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class MarketRelationship:
    """A causal or correlational relationship between market entities."""
    source: str
    target: str
    relationship: str  # "causes", "correlates", "dampens", "amplifies"
    strength: float  # 0.0 to 1.0
    lag_days: int = 0  # typical lag in trading days
    description: str = ""
    conditions: str = ""  # when this relationship is strongest


@dataclass
class SectorProfile:
    """Profile of an Indian market sector with key drivers."""
    name: str
    nse_indices: List[str]
    key_stocks: List[str]
    primary_drivers: List[str]
    fii_sensitivity: float  # -1 to 1 (negative = inverse)
    rate_sensitivity: float  # -1 to 1 (negative = benefits from rate cuts)
    usd_sensitivity: float  # -1 to 1 (negative = hurt by strong USD)
    budget_keywords: List[str] = field(default_factory=list)


class MarketKnowledgeGraph:
    """Static knowledge graph of Indian market structural relationships.

    This is the God's Eye equivalent of MiroFish's graph_builder + ontology_generator.
    Instead of building graphs dynamically from seed data, we encode domain expertise
    about Indian market structure that helps agents reason about cascading effects.
    """

    # =========================================================================
    # SECTOR PROFILES
    # =========================================================================
    SECTORS: Dict[str, SectorProfile] = {
        "banking": SectorProfile(
            name="Banking & Finance",
            nse_indices=["NIFTY BANK", "NIFTY FINANCIAL SERVICES"],
            key_stocks=["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"],
            primary_drivers=["RBI repo rate", "credit growth", "NPA trends", "NIM compression", "deposit rates"],
            fii_sensitivity=0.8,  # Heavy FII ownership
            rate_sensitivity=-0.7,  # Benefits from rate cuts (NIM expansion)
            usd_sensitivity=-0.3,
            budget_keywords=["banking regulation", "PSU recapitalization", "digital payments", "financial inclusion"],
        ),
        "it_services": SectorProfile(
            name="IT Services",
            nse_indices=["NIFTY IT"],
            key_stocks=["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
            primary_drivers=["US tech spending", "USDINR rate", "deal pipeline", "attrition", "AI disruption risk"],
            fii_sensitivity=0.9,  # Highest FII ownership
            rate_sensitivity=0.1,  # Low sensitivity
            usd_sensitivity=0.7,  # Benefits from weak INR (revenue in USD)
            budget_keywords=["IT tax", "SEZ policy", "digital India"],
        ),
        "pharma": SectorProfile(
            name="Pharmaceuticals",
            nse_indices=["NIFTY PHARMA"],
            key_stocks=["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"],
            primary_drivers=["FDA approvals", "US generic pricing", "USDINR", "API supply chain", "R&D pipeline"],
            fii_sensitivity=0.5,
            rate_sensitivity=0.0,
            usd_sensitivity=0.5,  # Benefits from weak INR
            budget_keywords=["healthcare spending", "pharma PLI", "drug pricing"],
        ),
        "auto": SectorProfile(
            name="Automobiles",
            nse_indices=["NIFTY AUTO"],
            key_stocks=["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO"],
            primary_drivers=["interest rates", "rural demand", "commodity prices", "EV transition", "monsoon"],
            fii_sensitivity=0.4,
            rate_sensitivity=-0.6,  # Rate cuts boost auto loans
            usd_sensitivity=-0.3,  # Import costs for components
            budget_keywords=["auto scrappage", "EV subsidy", "road cess", "emission norms"],
        ),
        "realty": SectorProfile(
            name="Real Estate",
            nse_indices=["NIFTY REALTY"],
            key_stocks=["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE"],
            primary_drivers=["home loan rates", "regulatory approvals", "DII/HNI demand", "RERA compliance", "unsold inventory"],
            fii_sensitivity=0.3,
            rate_sensitivity=-0.9,  # Most rate-sensitive sector
            usd_sensitivity=-0.1,
            budget_keywords=["affordable housing", "stamp duty", "RERA", "real estate tax"],
        ),
        "metals": SectorProfile(
            name="Metals & Mining",
            nse_indices=["NIFTY METAL"],
            key_stocks=["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC"],
            primary_drivers=["China demand", "global commodity prices", "infrastructure spending", "anti-dumping duties"],
            fii_sensitivity=0.6,
            rate_sensitivity=-0.2,
            usd_sensitivity=-0.5,  # Commodity prices in USD
            budget_keywords=["infrastructure", "steel duty", "mining policy", "PLI metals"],
        ),
        "fmcg": SectorProfile(
            name="FMCG / Consumer Staples",
            nse_indices=["NIFTY FMCG"],
            key_stocks=["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR"],
            primary_drivers=["rural consumption", "monsoon", "input costs", "distribution reach", "premiumization"],
            fii_sensitivity=0.5,
            rate_sensitivity=0.1,  # Defensive, low sensitivity
            usd_sensitivity=-0.2,  # Import costs for raw materials
            budget_keywords=["rural spending", "GST rates", "sin tax", "agriculture"],
        ),
        "energy": SectorProfile(
            name="Oil, Gas & Energy",
            nse_indices=["NIFTY ENERGY"],
            key_stocks=["RELIANCE", "ONGC", "BPCL", "IOC", "NTPC"],
            primary_drivers=["crude oil prices", "government subsidy policy", "gas pricing", "renewable transition", "refining margins"],
            fii_sensitivity=0.5,
            rate_sensitivity=-0.2,
            usd_sensitivity=-0.7,  # Oil priced in USD
            budget_keywords=["fuel subsidy", "windfall tax", "green energy", "gas pricing"],
        ),
        "nbfc": SectorProfile(
            name="NBFCs / Shadow Banking",
            nse_indices=["NIFTY FINANCIAL SERVICES"],
            key_stocks=["BAJFINANCE", "BAJAJFINSV", "SHRIRAMFIN", "MUTHOOTFIN", "CHOLAFIN"],
            primary_drivers=["RBI liquidity", "AUM growth", "asset quality", "regulatory tightening", "cost of funds"],
            fii_sensitivity=0.6,
            rate_sensitivity=-0.8,  # Very rate sensitive
            usd_sensitivity=-0.2,
            budget_keywords=["NBFC regulation", "microfinance", "digital lending"],
        ),
    }

    # =========================================================================
    # CAUSAL CHAINS — How shocks propagate through Indian markets
    # =========================================================================
    CAUSAL_CHAINS: List[MarketRelationship] = [
        # --- RBI Policy Cascades ---
        MarketRelationship("RBI_rate_cut", "banking_NIM", "amplifies", 0.8, 0,
                           "Rate cuts widen NIMs as lending rates adjust faster than deposit rates",
                           "Strongest when banks have fixed-rate deposits"),
        MarketRelationship("RBI_rate_cut", "auto_demand", "amplifies", 0.6, 30,
                           "Lower EMIs boost vehicle sales with 1-month lag",
                           "Strongest for passenger vehicles and 2-wheelers"),
        MarketRelationship("RBI_rate_cut", "realty_demand", "amplifies", 0.9, 60,
                           "Home loan affordability improves, strongest rate-sensitive sector",
                           "Effect amplified when builder inventory is high"),
        MarketRelationship("RBI_rate_cut", "nbfc_cost_of_funds", "dampens", 0.7, 15,
                           "Lower cost of funds improves NBFC spreads",
                           "NBFCs with higher share of bank borrowing benefit most"),
        MarketRelationship("RBI_rate_cut", "inr_weakness", "amplifies", 0.4, 0,
                           "Rate differential narrows, capital outflows increase INR pressure"),

        # --- FII Flow Cascades ---
        MarketRelationship("FII_outflow", "large_cap_pressure", "amplifies", 0.9, 0,
                           "FIIs hold ~20% of free float in large caps, selling creates direct price pressure"),
        MarketRelationship("FII_outflow", "INR_depreciation", "amplifies", 0.7, 0,
                           "Dollar demand from FII repatriation weakens INR"),
        MarketRelationship("FII_outflow", "DII_absorption", "dampens", 0.6, 1,
                           "DIIs typically absorb FII selling via SIP flows with 1-day lag",
                           "Limited by DII cash deployment mandates"),
        MarketRelationship("FII_outflow", "it_services_boost", "amplifies", 0.3, 5,
                           "INR weakness from FII selling benefits IT exporters",
                           "Only significant in sustained outflow periods"),
        MarketRelationship("FII_outflow", "retail_panic", "amplifies", 0.5, 2,
                           "Retail F&O traders panic-sell after seeing FII data with 2-day lag",
                           "Strongest during expiry weeks"),

        # --- Global Contagion ---
        MarketRelationship("US_rate_hike", "FII_outflow", "amplifies", 0.8, 5,
                           "Higher US yields attract capital away from EM including India"),
        MarketRelationship("DXY_strength", "INR_weakness", "amplifies", 0.9, 0,
                           "Dollar strength directly pressures all EM currencies"),
        MarketRelationship("DXY_strength", "commodity_weakness", "amplifies", 0.7, 0,
                           "Strong dollar depresses commodity prices globally"),
        MarketRelationship("China_slowdown", "metals_demand", "dampens", 0.8, 15,
                           "China consumes ~50% of global metals, slowdown hits Indian metal exporters"),
        MarketRelationship("oil_spike", "india_cad", "amplifies", 0.9, 0,
                           "India imports ~85% of oil, spike directly worsens current account deficit"),

        # --- Budget / Fiscal ---
        MarketRelationship("capex_boost", "infra_stocks", "amplifies", 0.8, 0,
                           "Government capex directly flows to L&T, railways, defense, roads"),
        MarketRelationship("tax_cut_corporate", "earnings_upgrade", "amplifies", 0.7, 0,
                           "Direct EPS boost across all sectors"),
        MarketRelationship("tax_cut_personal", "consumption_boost", "amplifies", 0.5, 30,
                           "More disposable income flows to FMCG, auto, retail"),
        MarketRelationship("wealth_tax_fear", "promoter_selling", "amplifies", 0.6, 0,
                           "Wealth tax proposals trigger promoter stake sales"),
        MarketRelationship("fiscal_deficit_blowout", "bond_yield_spike", "amplifies", 0.7, 0,
                           "Higher borrowing pressures yields, negative for rate-sensitive sectors"),

        # --- Expiry Dynamics ---
        MarketRelationship("expiry_approach", "gamma_exposure", "amplifies", 0.8, 0,
                           "Options gamma increases as DTE decreases, amplifying moves near strikes",
                           "Strongest for weekly expiry on Thursday"),
        MarketRelationship("max_pain_magnet", "spot_convergence", "amplifies", 0.5, 0,
                           "Market makers' hedging activity pulls spot toward max pain",
                           "Effect strongest in last 2 hours of expiry day"),
        MarketRelationship("high_pcr", "short_covering_rally", "amplifies", 0.6, 0,
                           "High PCR indicates excessive put writing, short covering drives rallies"),
        MarketRelationship("low_pcr", "call_unwinding_selloff", "amplifies", 0.6, 0,
                           "Low PCR means excessive call writing, unwinding drives selloffs"),

        # --- Corporate / Promoter ---
        MarketRelationship("promoter_pledge_increase", "stock_pressure", "amplifies", 0.7, 0,
                           "Rising pledges signal financial stress, trigger margin calls in crashes"),
        MarketRelationship("bulk_deal_sell", "near_term_weakness", "amplifies", 0.5, 0,
                           "Large block sales create short-term supply pressure"),
        MarketRelationship("corporate_governance_shock", "sector_rotation", "amplifies", 0.6, 5,
                           "Governance failures (Adani-style) trigger rotation away from affected group"),
    ]

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    @classmethod
    def get_sector(cls, sector_key: str) -> Optional[SectorProfile]:
        """Get sector profile by key."""
        return cls.SECTORS.get(sector_key)

    @classmethod
    def get_relationships_for_event(cls, event_key: str) -> List[MarketRelationship]:
        """Get all causal chains triggered by a market event."""
        return [r for r in cls.CAUSAL_CHAINS if event_key.lower() in r.source.lower()]

    @classmethod
    def get_relationships_affecting(cls, target_key: str) -> List[MarketRelationship]:
        """Get all relationships that affect a given target."""
        return [r for r in cls.CAUSAL_CHAINS if target_key.lower() in r.target.lower()]

    @classmethod
    def get_context_for_agent(cls, agent_key: str, context: str) -> str:
        """Build knowledge context string for a specific agent archetype.

        This is the key method — it selects and formats the most relevant
        structural knowledge for each agent type, given the current market context.
        """
        context_lower = context.lower() if context else "normal"

        if agent_key == "FII":
            return cls._build_fii_context(context_lower)
        elif agent_key == "DII":
            return cls._build_dii_context(context_lower)
        elif agent_key == "RETAIL_FNO":
            return cls._build_retail_context(context_lower)
        elif agent_key == "PROMOTER":
            return cls._build_promoter_context(context_lower)
        elif agent_key == "RBI":
            return cls._build_rbi_context(context_lower)
        return ""

    @classmethod
    def _build_fii_context(cls, context: str) -> str:
        """FII agent cares about: USD flows, EM rotation, sectoral ownership."""
        lines = ["STRUCTURAL MARKET KNOWLEDGE (Indian Market Relationships):"]

        # FII-sensitive sectors
        high_fii = [(k, s) for k, s in cls.SECTORS.items() if s.fii_sensitivity >= 0.7]
        lines.append(f"High FII-ownership sectors (most affected by FII flows): "
                     f"{', '.join(f'{s.name} ({s.fii_sensitivity:.0%})' for k, s in high_fii)}")

        # Context-specific chains
        if "fii" in context or "outflow" in context:
            chains = cls.get_relationships_for_event("FII_outflow")
            for c in chains:
                lines.append(f"  - FII selling → {c.target}: {c.description} (strength: {c.strength:.0%}, lag: {c.lag_days}d)")

        if "global" in context or "crisis" in context:
            chains = cls.get_relationships_for_event("DXY_strength") + cls.get_relationships_for_event("US_rate")
            for c in chains:
                lines.append(f"  - {c.source} → {c.target}: {c.description}")

        lines.append(f"IT services benefit from INR weakness (USD revenue): {cls.SECTORS['it_services'].usd_sensitivity:.0%} sensitivity")
        return "\n".join(lines)

    @classmethod
    def _build_dii_context(cls, context: str) -> str:
        """DII agent cares about: SIP flows, valuation support, sector rotation."""
        lines = ["STRUCTURAL MARKET KNOWLEDGE (Indian Market Relationships):"]

        lines.append("DII absorption capacity: SIP flows provide ~₹15,000-20,000 Cr/month steady buying")
        lines.append("DII typically absorbs FII selling with 1-day lag (deployment mandates)")

        # Rate-sensitive sectors (DII rotates into these on rate cuts)
        rate_sensitive = [(k, s) for k, s in cls.SECTORS.items() if s.rate_sensitivity <= -0.5]
        lines.append(f"Most rate-sensitive sectors (DII overweights on rate cuts): "
                     f"{', '.join(f'{s.name} ({s.rate_sensitivity:.0%})' for k, s in rate_sensitive)}")

        if "rbi" in context or "dovish" in context:
            chains = cls.get_relationships_for_event("RBI_rate_cut")
            for c in chains[:4]:
                lines.append(f"  - Rate cut → {c.target}: {c.description} (lag: {c.lag_days}d)")

        if "budget" in context:
            chains = cls.get_relationships_for_event("capex_boost") + cls.get_relationships_for_event("tax_cut")
            for c in chains:
                lines.append(f"  - {c.source} → {c.target}: {c.description}")

        return "\n".join(lines)

    @classmethod
    def _build_retail_context(cls, context: str) -> str:
        """Retail F&O agent cares about: expiry dynamics, gamma, max pain."""
        lines = ["STRUCTURAL MARKET KNOWLEDGE (Expiry & F&O Dynamics):"]

        # Always include expiry mechanics
        expiry_chains = cls.get_relationships_for_event("expiry") + cls.get_relationships_for_event("max_pain")
        for c in expiry_chains:
            lines.append(f"  - {c.source}: {c.description}")
            if c.conditions:
                lines.append(f"    Condition: {c.conditions}")

        # PCR dynamics
        pcr_chains = cls.get_relationships_for_event("pcr") + cls.get_relationships_for_event("high_pcr") + cls.get_relationships_for_event("low_pcr")
        for c in pcr_chains:
            lines.append(f"  - {c.source}: {c.description}")

        if "fii" in context or "outflow" in context:
            lines.append("  - FII selling → Retail panic: Retail F&O traders panic-sell after seeing FII data (2-day lag)")

        return "\n".join(lines)

    @classmethod
    def _build_promoter_context(cls, context: str) -> str:
        """Promoter agent cares about: pledge ratios, block deals, governance."""
        lines = ["STRUCTURAL MARKET KNOWLEDGE (Promoter & Corporate Dynamics):"]

        promoter_chains = cls.get_relationships_for_event("promoter") + cls.get_relationships_for_event("bulk_deal") + cls.get_relationships_for_event("corporate_governance")
        for c in promoter_chains:
            lines.append(f"  - {c.source}: {c.description}")

        if "budget" in context:
            wealth_chains = cls.get_relationships_for_event("wealth_tax")
            for c in wealth_chains:
                lines.append(f"  - {c.source} → {c.target}: {c.description}")

        return "\n".join(lines)

    @classmethod
    def _build_rbi_context(cls, context: str) -> str:
        """RBI agent cares about: inflation, forex reserves, systemic risk."""
        lines = ["STRUCTURAL MARKET KNOWLEDGE (Monetary Policy Cascades):"]

        rbi_chains = cls.get_relationships_for_event("RBI_rate_cut")
        for c in rbi_chains:
            lines.append(f"  - Rate cut → {c.target}: {c.description} (strength: {c.strength:.0%}, lag: {c.lag_days}d)")

        # Oil / CAD
        oil_chains = cls.get_relationships_for_event("oil_spike")
        for c in oil_chains:
            lines.append(f"  - {c.source}: {c.description}")

        lines.append("RBI forex intervention: ~$600B reserves, intervenes when INR volatility > 1% intraday")
        lines.append("Inflation target: 4% ±2% (CPI), breaches trigger hawkish response")

        if "fiscal" in context or "budget" in context:
            fiscal_chains = cls.get_relationships_for_event("fiscal_deficit")
            for c in fiscal_chains:
                lines.append(f"  - {c.source} → {c.target}: {c.description}")

        return "\n".join(lines)

    @classmethod
    def get_affected_sectors(cls, context: str) -> List[Dict]:
        """Get sectors most affected by the current market context, with direction."""
        context_lower = context.lower() if context else "normal"
        affected = []

        for key, sector in cls.SECTORS.items():
            impact = 0.0
            reasons = []

            if "rbi" in context_lower or "dovish" in context_lower or "rate_cut" in context_lower:
                impact += sector.rate_sensitivity * -0.5  # Rate cut → negative sensitivity = positive impact
                if sector.rate_sensitivity <= -0.5:
                    reasons.append(f"Rate-sensitive ({sector.rate_sensitivity:.0%})")

            if "fii" in context_lower or "outflow" in context_lower:
                impact += sector.fii_sensitivity * -0.3  # FII outflow hurts high-FII sectors
                if sector.fii_sensitivity >= 0.7:
                    reasons.append(f"High FII ownership ({sector.fii_sensitivity:.0%})")

            if "global" in context_lower or "crisis" in context_lower or "dxy" in context_lower:
                impact += sector.usd_sensitivity * -0.3  # USD strength hurts USD-negative sectors
                if abs(sector.usd_sensitivity) >= 0.5:
                    reasons.append(f"USD sensitivity ({sector.usd_sensitivity:.0%})")

            if "budget" in context_lower and "positive" in context_lower:
                if "infra" in " ".join(sector.budget_keywords).lower() or "capex" in " ".join(sector.budget_keywords).lower():
                    impact += 0.3
                    reasons.append("Direct budget beneficiary")

            if abs(impact) > 0.1:
                affected.append({
                    "sector": sector.name,
                    "impact": round(impact, 2),
                    "direction": "positive" if impact > 0 else "negative",
                    "reasons": reasons,
                })

        return sorted(affected, key=lambda x: abs(x["impact"]), reverse=True)
