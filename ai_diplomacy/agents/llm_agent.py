"""
LLM-based agent implementation.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

from ai_diplomacy.agents.base import BaseAgent
from ai_diplomacy.agents.llm.prompt.strategy import JinjaPromptStrategy, PromptStrategy

if TYPE_CHECKING:
    from ai_diplomacy.domain import DiploMessage, Order, PhaseState


logger = logging.getLogger(__name__)

__all__ = ["LLMAgent"]


class LLMAgent(BaseAgent):
    """
    LLM-based diplomacy agent that implements the BaseAgent interface.
    """

    prompt_strategy: PromptStrategy

    def __init__(
        self,
        agent_id: str,
        country: str,
    ):
        """
        Initialize the LLM agent.
        """
        super().__init__(agent_id=agent_id, country=country)
        self.prompt_strategy = JinjaPromptStrategy()
        self.country = country
        # TODO: Restore state, LLM coordinator, etc.

    async def decide_orders(self, phase: "PhaseState") -> List["Order"]:
        """
        Decide what orders to submit for the current phase.
        """
        logger.info(f"[{self.country}] Deciding orders for phase {phase.key.name}")

        my_units = phase.board.get_units(self.country)
        if not my_units:
            logger.info(f"[{self.country}] No units to command")
            return []

        prompt = self.prompt_strategy.for_orders(phase=phase, power=self.country)
        logger.debug("Generated prompt for orders:\n%s", prompt)

        # TODO: Here you would call the LLM with the prompt
        # For now, returning an empty list to satisfy the interface.
        return []

    async def negotiate(self, phase: "PhaseState") -> List["DiploMessage"]:
        """
        Generate diplomatic messages for the current phase.
        """
        # TODO: Implement negotiation logic using a prompt strategy
        return []
