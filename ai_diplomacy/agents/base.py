"""
Abstract base agent interface.
Defines the contract all agents must implement without coupling to specific LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..core.state import PhaseState

__all__ = ["Order", "Message", "BaseAgent"]


class Order:
    """Represents a single diplomatic order."""

    def __init__(self, order_text: str):
        self.order_text = order_text.strip()

    def __str__(self) -> str:
        return self.order_text

    def __repr__(self) -> str:
        return f"Order('{self.order_text}')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Order):
            return self.order_text == other.order_text
        if isinstance(other, str):
            return self.order_text == other
        return False

    def __hash__(self) -> int:
        return hash(self.order_text)


class Message:
    """Represents a diplomatic message between powers."""

    def __init__(self, recipient: str, content: str, message_type: str = "private"):
        self.recipient = recipient
        self.content = content
        self.message_type = message_type  # "private" or "global"

    def to_dict(self) -> Dict[str, str]:
        return {
            "recipient": self.recipient,
            "content": self.content,
            "message_type": self.message_type,
        }

    def __repr__(self) -> str:
        return f"Message(recipient='{self.recipient}', content='{self.content}', message_type='{self.message_type}')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Message):
            return (
                self.recipient == other.recipient
                and self.content == other.content
                and self.message_type == other.message_type
            )
        return False

    def __hash__(self) -> int:
        return hash((self.recipient, self.content, self.message_type))


class BaseAgent(ABC):
    """
    Abstract base class for all diplomacy agents.

    Key principles:
    - Agents receive frozen PhaseState objects (no direct game access)
    - Agents return orders and messages (no side effects)
    - Agents can maintain internal state but must not modify game state
    - Agent API is stable across different implementations (LLM, scripted, etc.)
    """

    def __init__(self, agent_id: str, country: str):
        """
        Initialize the agent.

        Args:
            agent_id: Unique identifier for this agent instance
            country: The country/power this agent represents (e.g., "FRANCE")
        """
        self.agent_id = agent_id
        self.country = country.upper()
        self.model_id: Optional[str] = None  # Will be set by concrete implementations

    @abstractmethod
    async def decide_orders(self, phase: PhaseState) -> List[Order]:
        """
        Decide what orders to submit for the current phase.

        Args:
            phase: Immutable snapshot of current game state

        Returns:
            List of orders to submit
        """
        pass

    @abstractmethod
    async def negotiate(self, phase: PhaseState) -> List[Message]:
        """
        Generate diplomatic messages to send to other powers.

        Args:
            phase: Immutable snapshot of current game state

        Returns:
            List of messages to send
        """
        pass

    @abstractmethod
    async def update_state(
        self, phase: PhaseState, events: List[Dict[str, Any]]
    ) -> None:
        """
        Update internal agent state based on phase results and events.

        Args:
            phase: The phase that just completed
            events: List of events that occurred (orders resolved, messages sent, etc.)
        """
        pass

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Return basic information about this agent.

        Returns:
            Dictionary with agent metadata
        """
        return {
            "agent_id": self.agent_id,
            "country": self.country,
            "type": self.__class__.__name__,
        }
