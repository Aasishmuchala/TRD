"""Base agent class for all market simulation agents."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from app.api.schemas import AgentResponse, MarketInput


class BaseAgent(ABC):
    """Abstract base class for all market agents.

    TODO: ARCH-C1 — All 6 LLM agents (FII, DII, Retail, Promoter, RBI, NewsEvent,
    StockOptions) duplicate _call_llm, _parse_response, _consensus_direction, and the
    sampling/consensus loop in analyze(). These should be extracted into BaseAgent as
    shared methods once the agent prompts are stable. Estimated dedup: ~200 lines per
    agent → ~50 lines each. Defer until agent prompt tuning is complete to avoid
    breaking functionality mid-iteration.
    """

    def __init__(
        self,
        name: str,
        persona: str,
        decision_framework: str,
        risk_appetite: str,
        time_horizon: str,
        agent_type: str,
    ):
        """Initialize base agent.

        Args:
            name: Agent name
            persona: Agent persona description
            decision_framework: How the agent makes decisions
            risk_appetite: Conservative/Moderate/Aggressive
            time_horizon: Intraday/Weekly/Quarterly/Yearly
            agent_type: QUANT or LLM
        """
        self.name = name
        self.persona = persona
        self.decision_framework = decision_framework
        self.risk_appetite = risk_appetite
        self.time_horizon = time_horizon
        self.agent_type = agent_type

    @abstractmethod
    async def analyze(
        self,
        market_data: MarketInput,
        round_num: int = 1,
        other_agents_output: Optional[Dict[str, AgentResponse]] = None,
        enriched_context: Optional[str] = None,
    ) -> AgentResponse:
        """Analyze market data and return trading direction.

        Args:
            market_data: Current market data
            round_num: Current interaction round (1-3)
            other_agents_output: Responses from other agents in previous rounds
            enriched_context: Pre-computed signals, knowledge graph context,
                            and past performance memory from ProfileGenerator

        Returns:
            AgentResponse with direction, conviction, and reasoning
        """
        pass

    def _validate_response(self, response: AgentResponse) -> bool:
        """Validate agent response structure."""
        required_fields = [
            "agent_name",
            "agent_type",
            "direction",
            "conviction",
            "reasoning",
            "key_triggers",
            "time_horizon",
        ]
        for field in required_fields:
            if not hasattr(response, field):
                return False
        if response.conviction < 0 or response.conviction > 100:
            return False
        return True
