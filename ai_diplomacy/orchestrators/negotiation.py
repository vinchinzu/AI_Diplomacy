import logging
import asyncio
from typing import List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from diplomacy import Game
    from ..game_history import GameHistory
    from ..agents.llm_agent import LLMAgent # For type checking agent
    from ..agents.base import Message # For type checking messages_list_objects
    from ..core.state import PhaseState # For type checking current_phase_state
    from ..services.config import GameConfig # For num_negotiation_rounds
    from ..agent_manager import AgentManager # For get_agent

logger = logging.getLogger(__name__)

async def perform_negotiation_rounds(
    game: "Game",
    game_history: "GameHistory",
    agent_manager: "AgentManager", # Added
    active_powers: List[str], # Added
    config: "GameConfig" # Added for num_negotiation_rounds
):
    current_phase_name = game.get_current_phase()
    logger.info(f"Performing negotiation rounds for phase: {current_phase_name}")

    # Ensure the phase is known to GameHistory before adding messages.
    game_history.add_phase(current_phase_name)

    num_rounds = max(1, getattr(config, "num_negotiation_rounds", 1))

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
                    current_phase_state = PhaseState.from_game(game)

                    if isinstance(agent, LLMAgent):
                        messages_list_objects: List[Message] = await asyncio.wait_for(
                            agent.negotiate(current_phase_state),
                            timeout=120.0,
                        )
                        messages_as_dicts = []
                        for msg_obj in messages_list_objects:
                            messages_as_dicts.append(
                                {
                                    "recipient": msg_obj.recipient,
                                    "content": msg_obj.content,
                                    "message_type": msg_obj.message_type,
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
                    logger.error(
                        f"❌ Timeout generating messages for {power_name} (round {round_num})"
                    )
                    all_proposed_messages[power_name] = []
                except Exception as e:
                    logger.error(
                        f"❌ Error generating messages for {power_name} (round {round_num}): {e}",
                        exc_info=True,
                    )
                    all_proposed_messages[power_name] = []
            else:
                logger.warning(
                    f"No agent found for active power {power_name} during message generation."
                )
                all_proposed_messages[power_name] = []

        for sender_power, messages_to_send_dicts in all_proposed_messages.items():
            for msg_dict in messages_to_send_dicts:
                recipient = msg_dict.get("recipient", "GLOBAL").upper()
                content = msg_dict.get("content", "")
                
                if recipient != "GLOBAL" and recipient not in active_powers:
                    logger.warning(
                        f"[{sender_power}] Tried to send message to invalid/inactive recipient '{recipient}'. Skipping."
                    )
                    continue

                game_history.add_message(
                    current_phase_name, sender_power, recipient, content
                )
                logger.debug(
                    f"Message from {sender_power} to {recipient}: {content[:75]}..."
                )

        if round_num < num_rounds:
            logger.info(
                f"End of Negotiation Round {round_num}. Next round starting..."
            )
        else:
            logger.info(f"Final Negotiation Round {round_num} completed.") 