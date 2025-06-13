"""
Generates and records summaries of game phases from a specific power's perspective.

This module provides the PhaseSummaryGenerator class, which uses an LLM to create
a diary-like entry reflecting on the events, orders, and negotiations of a completed
game phase. This summary is then recorded in the game history.
"""

import logging
from typing import Optional, Dict, List, TYPE_CHECKING, Any
from .services import LLMCoordinator
from . import llm_utils

if TYPE_CHECKING:
    from diplomacy import Game
    from .game_history import GameHistory, Phase  # Added Phase for type hint
    from .game_config import GameConfig

logger = logging.getLogger(__name__)

__all__ = ["PhaseSummaryGenerator"]


class PhaseSummaryGenerator:
    """
    Generates and records a summary of a game phase for a specific power.
    This was previously handled by phase_summary_callback in lm_game.py.
    """

    def __init__(
        self,
        llm_coordinator: "LLMCoordinator",
        game_config: "GameConfig",
        power_name: str,
    ):
        """
        Initializes the PhaseSummaryGenerator.

        Args:
            llm_coordinator: The LLM coordinator to use for API calls.
            game_config: The global game configuration object.
            power_name: The name of the power for whom the summary/diary is being generated.
        """
        self.llm_coordinator = llm_coordinator
        self.game_config = game_config
        self.power_name = power_name
        # Load the prompt template
        self.prompt_template = llm_utils.load_prompt_file("phase_result_diary_prompt.txt")

    def _get_all_orders_for_phase(self, game_history: "GameHistory", phase_name: str) -> Dict[str, List[str]]:
        """
        Helper to retrieve all orders for a given phase from game history.
        """
        phase_data: Optional["Phase"] = game_history.get_phase_by_name(phase_name)
        if phase_data and phase_data.orders_by_power:
            return phase_data.orders_by_power

        # Fallback if not in history (e.g. very first phase, or if history population is delayed)
        # This part might need adjustment based on when orders are added to GameHistory
        # For now, assume GameHistory is up-to-date when this is called.
        logger.warning(
            f"[{self.power_name}] Orders for phase {phase_name} not found in game_history.orders_by_power. This might be normal for initial phases."
        )
        return {}

    async def generate_and_record_phase_summary(
        self,
        game: "Game",  # Current game state
        game_history: "GameHistory",  # History up to the phase *before* the one being summarized if current_short_phase is used
        phase_to_summarize_name: str,  # e.g., "SPRING 1901M" (Movement phase that just ended)
        # Summary text of what happened in the phase (e.g. from game engine or observer)
        # This was 'phase_summary_text' in original lm_game.py, passed to phase_result_diary
        phase_events_summary_text: str,
        all_orders_for_phase: Dict[str, List[str]],  # Orders for the phase being summarized
    ) -> str:
        """
        Generates a phase result diary entry (which serves as a phase summary from the agent's perspective),
        records it in the game history, and returns the generated summary.

        Args:
            game: The current diplomacy.Game object.
            game_history: The GameHistory object.
            phase_to_summarize_name: The name of the phase that has just been completed and needs summarizing
                                     (e.g., the movement phase that just resolved).
            phase_events_summary_text: A textual summary of key events that occurred during this phase.
            all_orders_for_phase: A dictionary mapping power names to their orders for the phase being summarized.

        Returns:
            The generated summary string for the power, or an error message string.
        """
        logger.info(
            f"[{self.power_name}] Generating phase result diary (summary) for {phase_to_summarize_name}..."
        )

        # Prepare variables for the prompt, similar to original phase_summary_callback
        # The llm_interface for this power will use its own self.power_name, goals, relationships.

        # Format all orders for the prompt
        all_orders_formatted = ""
        for power, orders in all_orders_for_phase.items():
            orders_str = ", ".join(orders) if orders else "No orders"
            all_orders_formatted += f"{power}: {orders_str}\n"

        your_orders_str = (
            ", ".join(all_orders_for_phase.get(self.power_name, []))
            if all_orders_for_phase.get(self.power_name)
            else "No orders submitted by you"
        )

        # Get negotiations relevant to this phase (from history)
        # GameHistory needs a method to get messages *for a specific phase* easily
        # Assuming get_messages_by_phase exists or can be added to GameHistory
        messages_this_phase = game_history.get_messages_by_phase(
            phase_to_summarize_name
        )  # You'd need to implement/verify this

        your_negotiations_text = ""
        if messages_this_phase:
            for msg_obj in messages_this_phase:  # Assuming msg_obj has sender, recipient, content
                if msg_obj.sender == self.power_name:
                    your_negotiations_text += f"To {msg_obj.recipient}: {msg_obj.content}\n"
                elif msg_obj.recipient == self.power_name:
                    your_negotiations_text += f"From {msg_obj.sender}: {msg_obj.content}\n"
        if not your_negotiations_text:
            your_negotiations_text = "No negotiations involving your power recorded for this phase."

        agent_goals_str = "Goals not available to PhaseSummaryGenerator directly."
        agent_relationships_str = "Relationships not available to PhaseSummaryGenerator directly."

        # If game_config.agents exists and contains the current agent:
        if self.game_config.agents and self.power_name in self.game_config.agents:
            current_agent = self.game_config.agents[self.power_name]
            agent_goals_str = (
                "\n".join([f"- {g}" for g in current_agent.goals]) if current_agent.goals else "None"
            )
            agent_relationships_str = "\n".join([f"{p}: {r}" for p, r in current_agent.relationships.items()])
        else:
            logger.warning(
                f"Agent {self.power_name} not found in game_config.agents. Using placeholder goals/relationships for summary generation."
            )

        prompt_template_vars: Dict[str, Any] = {
            "power_name": self.power_name,
            "current_phase": phase_to_summarize_name,
            "phase_summary": phase_events_summary_text,  # This is the general summary of events
            "all_orders_formatted": all_orders_formatted,
            "your_negotiations": your_negotiations_text,
            "pre_phase_relationships": agent_relationships_str,  # Agent's relationships before this phase's impact
            "agent_goals": agent_goals_str,  # Agent's current goals
            "your_actual_orders": your_orders_str,
        }

        prompt = self.prompt_template.format(**prompt_template_vars)

        generated_summary = "(Error: LLM call not made due to refactoring)"  # Default error
        try:
            # Make the LLM call via the coordinator
            model_id_for_summary = (
                self.game_config.model_id
                if hasattr(self.game_config, "model_id") and self.game_config.model_id
                else "default_summary_model"
            )
            game_id_for_summary = (
                self.game_config.game_id if hasattr(self.game_config, "game_id") else "unknown_game"
            )

            generated_summary = await self.llm_coordinator.request(
                model_id=model_id_for_summary,
                prompt_text=prompt,
                system_prompt_text="You are a reflective diarist summarizing game events for your power.",
                game_id=game_id_for_summary,
                agent_name=self.power_name,
                phase_str=phase_to_summarize_name,
                request_identifier=f"{self.power_name}-{phase_to_summarize_name}-summary_gen",
            )
            logger.info(f"[{self.power_name}] LLM response for phase summary: {generated_summary[:100]}...")

        except Exception as e:
            logger.error(
                f"[{self.power_name}] Error during LLM call for phase summary: {e}",
                exc_info=True,
            )
            generated_summary = f"(Error: LLM call failed - {e})"

        if generated_summary and not generated_summary.startswith("(Error:"):
            game_history.add_phase_summary(phase_to_summarize_name, self.power_name, generated_summary)
            logger.info(
                f"[{self.power_name}] Generated and recorded phase summary/diary for {phase_to_summarize_name}."
            )
            return generated_summary
        else:
            logger.error(
                f"[{self.power_name}] Failed to generate phase summary/diary for {phase_to_summarize_name}. LLM response: {generated_summary}"
            )
            error_message = f"(Error: Failed to generate phase summary for {self.power_name} for {phase_to_summarize_name})"
            game_history.add_phase_summary(phase_to_summarize_name, self.power_name, error_message)
            return error_message
