from typing import List, Dict, Any
from .base import BaseAgent, Order, Message
from ..core.state import PhaseState

class NeutralAgent(BaseAgent):
    """
    An agent that represents a neutral power.
    It always issues HOLD orders for all its units and does not engage in negotiation.
    """

    def __init__(self, agent_id: str, country: str):
        super().__init__(agent_id, country)
        self.model_id = "neutral" # Explicitly set model_id for neutral type

    async def decide_orders(self, phase: PhaseState) -> List[Order]:
        """
        Decide what orders to submit for the current phase.
        Neutral agents always HOLD all their units.
        """
        orders = []
        power_state = phase.get_power_state(self.country)
        if power_state:
            for unit in power_state.units:
                # Assuming unit is a string like "A PAR", "F MAR", etc.
                # Or if unit is an object, it should have a 'location' or 'name' attribute.
                # For simplicity, let's assume unit string includes its location.
                # A HOLD order is just the unit itself.
                # Example: "A PAR H" or "F MAR H"
                # The diplomacy library expects orders like: "A PAR HLD"
                # Unit name is like "A PAR", "F MAR"
                orders.append(Order(f"{unit} HLD"))
        return orders

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
