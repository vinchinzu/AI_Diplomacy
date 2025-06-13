"""
Defines the strategy for transforming game state into LLM prompts.
"""
from __future__ import annotations

import dataclasses
from typing import Protocol

import jinja2

from ai_diplomacy.domain.phase import PhaseState

__all__ = ["PromptStrategy"]


TEMPLATES = jinja2.Environment(
    loader=jinja2.PackageLoader("ai_diplomacy.agents.llm.prompt", "templates"),
    autoescape=False,
)
ORDER_TEMPLATE = TEMPLATES.get_template("order_prompt.j2")
# TODO: Load other templates as they are integrated.


class PromptStrategy(Protocol):
    """
    An interface for generating prompts from game state.

    This protocol allows different prompt generation strategies to be used
    interchangeably by the LLM-based agent.
    """

    def for_orders(
        self,
        phase: PhaseState,
        power: str,
        *,
        goal_summary: str | None = None,
    ) -> str:
        """
        Generates the prompt for deciding orders.

        Args:
            phase: The current phase state of the game.
            power: The name of the power the agent is playing.
            goal_summary: A summary of the agent's current goals.

        Returns:
            The fully-rendered prompt text.
        """
        ...


@dataclasses.dataclass(frozen=True)
class JinjaPromptStrategy:
    """A prompt strategy that uses Jinja2 templates."""

    def for_orders(
        self,
        phase: PhaseState,
        power: str,
        *,
        goal_summary: str | None = None,
    ) -> str:
        """
        Generates the prompt for deciding orders using a Jinja2 template.
        """
        # This is a simplified context for demonstration.
        # A real implementation would extract more details from the PhaseState.
        context = {
            "country": power,
            "goals": goal_summary.split("\n") if goal_summary else [],
            "relationships": {},  # To be implemented
            "formatted_diary": "",  # To be implemented
            "context_text": f"It is {phase.key.season} {phase.key.year}, phase {phase.key.name}.",
            "tools_available": False,
        }
        return ORDER_TEMPLATE.render(context)
