"""
LLM-based agent that controls a bloc of multiple countries.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Dict, Any

from ai_diplomacy.agents.base import BaseAgent
from ai_diplomacy.agents.llm.prompt.strategy import JinjaPromptStrategy, PromptStrategy

if TYPE_CHECKING:
    from ai_diplomacy.domain import Order, PhaseState

logger = logging.getLogger(__name__)


class BlocLLMAgent(BaseAgent):
    """
    An LLM-based agent that controls a bloc of multiple countries.
    """

    prompt_strategy: PromptStrategy

    def __init__(
        self,
        agent_id: str,
        bloc_name: str,
        controlled_powers: List[str],
    ):
        if not controlled_powers:
            raise ValueError("BlocLLMAgent must have at least one controlled power.")

        # Use the first power as the "representative" for the BaseAgent
        super().__init__(agent_id, controlled_powers[0])

        self.bloc_name = bloc_name
        self.controlled_powers = [p.upper() for p in controlled_powers]
        self.prompt_strategy = JinjaPromptStrategy()
        logger.info(
            f"BlocLLMAgent '{self.agent_id}' initialized for bloc '{self.bloc_name}' "
            f"controlling {self.controlled_powers}."
        )

    async def decide_orders(self, phase: "PhaseState") -> List["Order"]:
        """
        Decides orders for the bloc.
        """
        logger.info(
            f"BlocLLMAgent '{self.agent_id}' ({self.bloc_name}) deciding orders "
            f"for {self.controlled_powers} in phase {phase.key.name}"
        )

        # In a real implementation, the prompt strategy would be designed
        # to handle a bloc of powers and return orders for all of them.
        # For now, we call the simple `for_orders` method as a placeholder.
        prompt = self.prompt_strategy.for_orders(phase=phase, power=self.bloc_name)
        logger.debug("Generated prompt for bloc orders:\n%s", prompt)

        # TODO: Here you would call the LLM and parse the response for all controlled powers.
        # Returning orders for the representative country only to satisfy the interface.
        return []

    def get_all_bloc_orders_for_phase(
        self,
        phase_key_tuple: tuple,  # This argument might need re-evaluation if phase state representation changes.
    ) -> Dict[str, List[Order]]:
        """
        Returns all cached orders for the bloc for a given phase.
        This is a placeholder and would need to be properly implemented.
        """
        logger.warning("get_all_bloc_orders_for_phase is a placeholder and not fully implemented.")
        return {}

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Return basic information about this agent.
        """
        return {
            "agent_id": self.agent_id,
            "bloc_name": self.bloc_name,
            "controlled_powers": self.controlled_powers,
            "agent_type": "BlocLLMAgent",
        }
