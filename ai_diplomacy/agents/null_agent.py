from typing import List, Dict, Any, Optional

from .base import BaseAgent, Order, Message
from diplomacy import Game
from ..core.state import PhaseState

class NullAgent(BaseAgent):
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
        """Generates hold orders for all units of the controlled power."""
        orders = []
        # self.country is the power_name for this agent, set in BaseAgent's __init__
        power_name_upper = self.country.upper()

        # Access units from PhaseState if available, otherwise need to adjust
        # Assuming PhaseState has a way to get units for a power.
        # For now, let's assume phase.get_units(power_name) exists or adapt based on PhaseState structure.
        # From the traceback, NullAgent was instantiated, so game.powers was likely available before.
        # Let's use a simplified approach for now assuming PhaseState provides units.
        # If PhaseState doesn't directly provide units like diplomacy.Game, this will need adjustment
        # based on PhaseState's actual API.
        # For now, we'll try to access units via phase.game.get_units if phase.game is the diplomacy.Game instance.
        
        current_game_state = phase.game # Assuming phase.game is the diplomacy.Game object

        if power_name_upper in current_game_state.powers:
            for unit in current_game_state.get_units(power_name_upper):
                orders.append(Order(f"{unit} H")) # Wrap in Order object
        return orders

    async def negotiate(self, phase: PhaseState) -> List[Message]:
        """NullAgent does not send messages."""
        return []

    async def update_state(
        self, phase: PhaseState, events: List[Dict[str, Any]]
    ) -> None:
        """NullAgent does not maintain complex internal state from game events."""
        pass # No state to update

    # Keeping existing helper methods if they were used by other parts,
    # but the abstract methods above are the primary interface.
    # The original generate_orders, generate_messages, etc., can be removed or kept as internal helpers
    # if decide_orders and negotiate call them. For NullAgent, the logic is simple enough to be direct.

    async def generate_orders(self, game: Game, power_name: str) -> List[str]:
        """Generates hold orders for all units of the controlled power. (Old method, can be removed)"""
        # This can be removed if decide_orders is self-contained
        orders_str = []
        if power_name.upper() in game.powers:
            for unit in game.get_units(power_name.upper()):
                orders_str.append(f"{unit} H")
        return orders_str

    async def generate_messages(
        self, game: Game, power_name: str, current_year: int, current_phase: str
    ) -> List[Message]:
        """NullAgent does not send messages. (Old method, can be removed)"""
        return []

    async def respond_to_messages(
        self, game: Game, power_name: str, received_messages: List[Message]
    ) -> List[Message]:
        """NullAgent does not respond to messages. (Old method, can be removed)"""
        return []
    
    async def plan_next_phase(
        self, game: Game, power_name: str, current_year: int, current_phase: str
    ) -> str:
        """NullAgent does not plan. (Old method, can be removed)"""
        return "No plan as this is a NullAgent."

    def get_model_id(self) -> Optional[str]:
        """NullAgent does not have a model ID."""
        return None 