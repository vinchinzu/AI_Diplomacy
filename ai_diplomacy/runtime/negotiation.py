import logging
import asyncio
from typing import List, Dict, TYPE_CHECKING
from .. import constants

from ai_diplomacy.domain import PhaseState, DiploMessage
from ..agents.llm_agent import LLMAgent  # Added this import
from ..game_config import GameConfig
from ..game_state import GameState
from .agents import get_agent_by_power

if TYPE_CHECKING:
    from diplomacy import Game
    from ..game_history import GameHistory
    from ..domain.state import PhaseState  # For type checking current_phase_state
    from ..services.config import GameConfig  # For num_negotiation_rounds
    from ..agent_manager import AgentManager  # For get_agent
"""
Handles the negotiation process between agents during a Diplomacy game phase.

This module provides the `perform_negotiation_rounds` asynchronous function,
which manages multiple rounds of message exchange between active agents,
allowing them to communicate and strategize.
"""

logger = logging.getLogger(__name__)

__all__ = ["perform_negotiation_rounds"]


async def perform_negotiation_rounds(
    game: "Game",
    phase: "PhaseState",
    game_history: "GameHistory",
    agent_manager: "AgentManager",  # Added
    active_powers: List[str],  # Added
    config: "GameConfig",  # Added for num_negotiation_rounds
):
    """
    Manages multiple rounds of diplomatic message exchange between active agents.

    For each round, it prompts each agent to generate messages, collects them,
    and then distributes them by adding them to the game history. This process
    repeats for a configured number of rounds.

    Args:
        game: The current diplomacy.Game object.
        phase: The current phase state
        game_history: The GameHistory object to record messages.
        agent_manager: The AgentManager to retrieve agent instances.
        active_powers: A list of power names that are currently active.
        config: The GameConfig object, used to determine the number of negotiation rounds.
    """
    current_phase_name = phase.name
    logger.info(f"Performing negotiation rounds for phase: {current_phase_name}")

    # Ensure the phase is known to GameHistory before adding messages.
    game_history.add_phase(current_phase_name)

    # Directly use num_negotiation_rounds from config.
    # GameConfig ensures this attribute exists and has a default if not set by args.
    num_rounds = config.num_negotiation_rounds

    for round_num in range(1, num_rounds + 1):
        logger.info(f"Negotiation Round {round_num}/{num_rounds}")

        all_proposed_messages: Dict[str, List[Dict[str, str]]] = {}

        for power_name in active_powers:
            agent = agent_manager.get_agent(power_name)
            if agent:
                logger.debug(
                    f"[Negotiation] Starting message generation for {power_name} (round {round_num})..."
                )
                try:
                    if isinstance(agent, LLMAgent):
                        messages_list_objects: List[DiploMessage] = await asyncio.wait_for(
                            agent.negotiate(phase),
                            timeout=constants.NEGOTIATION_MESSAGE_TIMEOUT_SECONDS,
                        )
                        messages_as_dicts = []
                        for msg_obj in messages_list_objects:
                            messages_as_dicts.append(
                                {
                                    constants.LLM_MESSAGE_KEY_RECIPIENT: msg_obj.recipient,
                                    constants.LLM_MESSAGE_KEY_CONTENT: msg_obj.content,
                                    constants.LLM_MESSAGE_KEY_TYPE: msg_obj.message_type,
                                }
                            )
                        all_proposed_messages[power_name] = messages_as_dicts
                        logger.debug(
                            f"✅ {power_name} (LLMAgent): Generated {len(messages_as_dicts)} messages (round {round_num})"
                        )
                    else:
                        logger.warning(
                            f"Agent {power_name} is not an LLMAgent. Skipping message generation. (Type: {type(agent)})"
                        )
                        all_proposed_messages[power_name] = []

                except asyncio.TimeoutError:
                    logger.error(f"❌ Timeout generating messages for {power_name} (round {round_num})")
                    all_proposed_messages[power_name] = []
                except Exception as e:
                    logger.error(
                        f"❌ Error generating messages for {power_name} (round {round_num}): {e}",
                        exc_info=True,
                    )
                    all_proposed_messages[power_name] = []
            else:
                logger.warning(f"No agent found for active power {power_name} during message generation.")
                all_proposed_messages[power_name] = []

        for sender_power, messages_to_send_dicts in all_proposed_messages.items():
            for msg_dict in messages_to_send_dicts:
                recipient = msg_dict.get(
                    constants.LLM_MESSAGE_KEY_RECIPIENT,
                    constants.MESSAGE_RECIPIENT_GLOBAL,
                ).upper()
                content = msg_dict.get(constants.LLM_MESSAGE_KEY_CONTENT, "")

                if recipient != constants.MESSAGE_RECIPIENT_GLOBAL and recipient not in active_powers:
                    logger.warning(
                        f"[{sender_power}] Tried to send message to invalid/inactive recipient '{recipient}'. Skipping."
                    )
                    continue

                game_history.add_message(current_phase_name, sender_power, recipient, content)
                logger.debug(f"Message from {sender_power} to {recipient}: {content[:75]}...")

        if round_num < num_rounds:
            logger.info(f"End of Negotiation Round {round_num}. Next round starting...")
        else:
            logger.info(f"Final Negotiation Round {round_num} completed.")


async def conduct_negotiations(
    game_config: "GameConfig",
    game: "GameState",
    game_history: "GameHistory",
    powers: List[str],
):
    """
    Args:
        game_config: The game configuration object.
        game: The current game state object.
        game_history: The history of the game.
        powers: The list of powers to run negotiations for.
    """
    current_phase = game.get_current_phase()
    logger.info(f"<{current_phase}> Conducting bilateral negotiations for powers: {powers}")

    # This example shows a simple loop; a more advanced implementation
    # could involve parallel execution or more complex scheduling.
    for power_name in powers:
        agent = get_agent_by_power(game_config, power_name)
        if not agent:
            logger.warning(
                f"Could not find agent for power '{power_name}' during negotiation phase. Skipping."
            )
            continue

        if not hasattr(agent, "negotiate"):
            logger.info(f"Agent for {power_name} does not have a 'negotiate' method. Skipping.")
            continue

        try:
            await agent.negotiate(game, game_history)
        except Exception as e:
            logger.error(f"Error during negotiation for {power_name}: {e}", exc_info=True)
