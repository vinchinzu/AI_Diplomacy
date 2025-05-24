from dotenv import load_dotenv
import logging
import asyncio
from typing import Dict, TYPE_CHECKING

from diplomacy.engine.message import Message, GLOBAL

from .agent import DiplomacyAgent
# from .clients import load_model_client # Removed obsolete import
from .utils import gather_possible_orders # load_prompt is not used here anymore

if TYPE_CHECKING:
    from .game_history import GameHistory
    from diplomacy import Game

logger = logging.getLogger("negotiations")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

load_dotenv()


async def conduct_negotiations(
    game: 'Game',
    agents: Dict[str, DiplomacyAgent],
    game_history: 'GameHistory',
    model_error_stats: Dict[str, Dict[str, int]],
    log_file_path: str,
    max_rounds: int = 3,
):
    """
    Conducts a round-robin conversation among all non-eliminated powers.
    Each power can send up to 'max_rounds' messages, choosing between private
    and global messages each turn. Uses asyncio for concurrent message generation.
    """
    logger.info("Starting negotiation phase.")

    active_powers = [
        p_name for p_name, p_obj in game.powers.items() if not p_obj.is_eliminated()
    ]
    eliminated_powers = [
        p_name for p_name, p_obj in game.powers.items() if p_obj.is_eliminated()
    ]
    
    logger.info(f"Active powers for negotiations: {active_powers}")
    if eliminated_powers:
        logger.info(f"Eliminated powers (skipped): {eliminated_powers}")
    else:
        logger.info("No eliminated powers yet.")

    # We do up to 'max_rounds' single-message turns for each power
    for round_index in range(max_rounds):
        logger.info(f"Negotiation Round {round_index + 1}/{max_rounds}")
        
        # Prepare tasks for asyncio.gather
        tasks = []
        power_names_for_tasks = []

        for power_name in active_powers:
            if power_name not in agents:
                logger.warning(f"Agent for {power_name} not found in negotiations. Skipping.")
                continue
            agent = agents[power_name]
            # client = agent.client # Removed obsolete client logic

            possible_orders = gather_possible_orders(game, power_name)
            # if not possible_orders: # Keep allowing message generation even if no orders
            #     logger.info(f"No orderable locations for {power_name}; skipping message generation.")
            #     continue
            board_state = game.get_state()

            # Append the coroutine to the tasks list
            tasks.append(
                agent.generate_messages( # Call the new agent method
                    game=game,
                    board_state=board_state,
                    # power_name is self.power_name in agent method
                    possible_orders=possible_orders, # Pass for context
                    game_history=game_history,
                    current_phase=game.current_short_phase,
                    log_file_path=log_file_path,
                    active_powers=active_powers,
                    # agent_goals, agent_relationships, agent_private_diary_str are accessed via self in agent method
                )
            )
            power_names_for_tasks.append(power_name)
            logger.debug(f"Prepared generate_messages task for {power_name}.")

        # Run tasks concurrently if any were created
        if tasks:
            logger.debug(f"Running {len(tasks)} conversation tasks concurrently...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            logger.debug("No conversation tasks to run for this round.")
            results = []

        # Process results
        for i, result in enumerate(results):
            power_name = power_names_for_tasks[i]
            agent = agents[power_name] # Get agent again for journaling
            model_id_for_stats = agent.model_id # Get model_id for stats

            if isinstance(result, Exception):
                logger.error(f"Error getting conversation reply for {power_name} (model: {model_id_for_stats}): {result}", exc_info=result)
                model_error_stats.setdefault(model_id_for_stats, {}).setdefault("conversation_errors", 0)
                model_error_stats[model_id_for_stats]["conversation_errors"] += 1
                messages = [] # Treat as no messages on error
            elif result is None: # Handle case where agent method might return None on internal error (though it should return list)
                 logger.warning(f"Received None instead of messages for {power_name} (model: {model_id_for_stats}).")
                 messages = []
                 model_error_stats.setdefault(model_id_for_stats, {}).setdefault("conversation_errors", 0)
                 model_error_stats[model_id_for_stats]["conversation_errors"] += 1
            else:
                messages = result # result is the list of message dicts from agent.generate_messages
                logger.debug(f"Received {len(messages)} message(s) from {power_name} (model: {model_id_for_stats}).")

            # Process the received messages (same logic as before)
            if messages:
                for message_dict in messages: # Changed variable name from message to message_dict
                    # Validate message structure
                    if not isinstance(message_dict, dict) or "content" not in message_dict:
                        logger.warning(f"Invalid message format received from {power_name}: {message_dict}. Skipping.")
                        continue

                    # Create an official message in the Diplomacy engine
                    # Determine recipient based on message type
                    # Ensure recipient is uppercase and valid
                    recipient_from_llm = str(message_dict.get("recipient", GLOBAL)).upper()
                    if recipient_from_llm not in ALL_POWERS and recipient_from_llm != GLOBAL:
                         logger.warning(f"Invalid recipient '{recipient_from_llm}' from LLM for {power_name}. Defaulting to GLOBAL.")
                         actual_recipient = GLOBAL
                    else:
                        actual_recipient = recipient_from_llm

                    if message_dict.get("message_type") == "private":
                        # If private, recipient must be a specific power, not GLOBAL
                        if actual_recipient == GLOBAL:
                            logger.warning(f"Private message from {power_name} had recipient GLOBAL. Sending globally due to ambiguity.")
                            # Or, could decide to not send, or pick a default like the first other active power.
                            # For now, send globally as a fallback, but this indicates an LLM issue.
                            pass # actual_recipient is already GLOBAL
                        elif actual_recipient == power_name: # Cannot send private to self
                            logger.warning(f"Private message from {power_name} to self. Skipping.")
                            continue
                    else: # Assume global if not explicitly private or type is missing/invalid
                        actual_recipient = GLOBAL
                        
                    diplo_message = Message(
                        phase=game.current_short_phase,
                        sender=power_name,
                        recipient=actual_recipient, 
                        message=message_dict.get("content", ""),
                        time_sent=None, 
                    )
                    game.add_message(diplo_message)
                    game_history.add_message(
                        game.current_short_phase,
                        power_name,
                        actual_recipient, 
                        message_dict.get("content", ""),
                    )
                    journal_recipient_log = f"to {actual_recipient}" if actual_recipient != GLOBAL else "globally"
                    agent.add_journal_entry(f"Sent message {journal_recipient_log} in {game.current_short_phase}: {message_dict.get('content', '')[:100]}...")
                    logger.info(f"[{power_name} -> {actual_recipient}] {message_dict.get('content', '')[:100]}...")
            else:
                logger.debug(f"No valid messages returned or error occurred for {power_name}.")

    logger.info("Negotiation phase complete.")
    # Add ALL_POWERS constant at the top of the file
    return game_history

ALL_POWERS = frozenset({"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"})
