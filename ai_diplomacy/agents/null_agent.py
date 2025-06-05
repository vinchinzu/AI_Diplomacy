from typing import List, Dict, Any, Optional

from .base import BaseAgent, Order, Message, HoldBehaviourMixin
from ..core.state import PhaseState

class NullAgent(BaseAgent, HoldBehaviourMixin):
    """
    An agent that represents an uncontrolled power or a power in civil disorder.
    It always issues hold orders and does not participate in negotiations.
    """

    def __init__(self, agent_id: str, power_name: str, game_config: Optional[Any] = None):
        super().__init__(agent_id, power_name)
        # self.power_name is already set by super().__init__ as self.country
        # self.game_config = game_config # Store if needed for other logic, not used currently by NullAgent
        # NullAgent does not use an LLM, so model_id and related attributes are not needed.

    async def decide_orders(self, phase: PhaseState) -> List[Order]:
        """Generates hold orders for all units of the controlled power using HoldBehaviourMixin."""
        return self.get_hold_orders(phase)

    async def negotiate(self, phase: PhaseState) -> List[Message]:
        """NullAgent does not send messages."""
        return []

    async def update_state(
        self, phase: PhaseState, events: List[Dict[str, Any]]
    ) -> None:
        """NullAgent does not maintain complex internal state from game events."""
        pass # No state to update

    def get_model_id(self) -> Optional[str]:
        """NullAgent does not have a model ID."""
        return None