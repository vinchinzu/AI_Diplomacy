from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING, Protocol, Optional

if TYPE_CHECKING:
    from ai_diplomacy.domain import DiploMessage, Order, PhaseState

__all__ = ["BaseAgent", "Agent"]


class Agent(Protocol):
    async def decide_orders(self, phase: "PhaseState") -> List["Order"]: ...
    async def receive_messages(self, msgs: List["DiploMessage"]) -> None: ...


class BaseAgent(ABC):
    """
    Abstract base class for all diplomacy agents.
    """

    def __init__(self, agent_id: str, country: str):
        self.agent_id = agent_id
        self.country = country.upper()
        self.model_id: Optional[str] = None

    @abstractmethod
    async def decide_orders(self, phase: "PhaseState") -> List["Order"]:
        pass

    @abstractmethod
    async def negotiate(self, phase: "PhaseState") -> List["DiploMessage"]:
        pass

    @abstractmethod
    async def update_state(self, phase: "PhaseState", events: list) -> None:
        pass

    def get_agent_info(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "country": self.country,
            "type": self.__class__.__name__,
        }
