from typing import List, Dict, Any
from .base import BaseAgent, Order, Message, HoldBehaviourMixin
from ..core.state import PhaseState


class NeutralAgent(BaseAgent, HoldBehaviourMixin):
    """
    An agent that represents a neutral power.
    It always issues HOLD orders for all its units and does not engage in negotiation.
    """

    def __init__(self, agent_id: str, country: str):
        super().__init__(agent_id, country)
        self.model_id = "neutral"  # Explicitly set model_id for neutral type

    async def decide_orders(self, phase: PhaseState) -> List[Order]:
        """
        Decide what orders to submit for the current phase.
        Neutral agents always HOLD all their units using HoldBehaviourMixin.
        """
        return self.get_hold_orders(phase)

    async def negotiate(self, phase: PhaseState) -> List[Message]:
        """
        Neutral agents do not negotiate.
        """
        return []

    async def update_state(
        self, phase: PhaseState, events: List[Dict[str, Any]]
    ) -> None:
        """
        Neutral agents do not maintain complex internal state based on game events.
        """
        pass

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Return basic information about this agent.
        """
        info = super().get_agent_info()
        info["type"] = "NeutralAgent"
        info["model_id"] = self.model_id
        return info
