from __future__ import annotations

"""
Abstract base agent interface.
Defines the contract all agents must implement without coupling to specific LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING

# Import PhaseState directly
from ..core.state import PhaseState

# TYPE_CHECKING block for Order and Message
if TYPE_CHECKING:
    from ..core.order import Order
    from ..core.message import Message

__all__ = ["BaseAgent"]


class BaseAgent(ABC):
    """
    Abstract base class for all diplomacy agents.
    """

    def __init__(self, agent_id: str, country: str):
        self.agent_id = agent_id
        self.country = country.upper()  # Ensure country is uppercase
        self.model_id: Optional[str] = None

    @abstractmethod
    async def decide_orders(self, phase: PhaseState) -> List["Order"]:  # Use quotes for forward ref
        pass

    @abstractmethod
    async def negotiate(self, phase: PhaseState) -> List["Message"]:  # Use quotes for forward ref
        pass

    @abstractmethod
    async def update_state(self, phase: PhaseState, events: List[Dict[str, Any]]) -> None:
        pass

    def get_agent_info(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "country": self.country,
            "type": self.__class__.__name__,
        }
