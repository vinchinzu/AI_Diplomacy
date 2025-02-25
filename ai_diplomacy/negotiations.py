from dotenv import load_dotenv
import logging
import concurrent.futures

from diplomacy.engine.message import Message, GLOBAL

from .clients import load_model_client
from .utils import gather_possible_orders

logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

load_dotenv()


def conduct_negotiations(game, game_history, model_error_stats, max_rounds=3):
    """
    Conducts a round-robin conversation among all non-eliminated powers.
    Each power can send up to 'max_rounds' messages, choosing between private
    and global messages each turn.
    """
    logger.info(f"DIPLOMACY | Starting negotiation phase with {max_rounds} rounds")

    # Conversation messages are kept in a local list ONLY to build conversation_so_far text.
    conversation_messages = []

    active_powers = [
        p_name for p_name, p_obj in game.powers.items() if not p_obj.is_eliminated()
    ]
    
    logger.debug(f"DIPLOMACY | Found {len(active_powers)} active powers for negotiations")

    # We do up to 'max_rounds' single-message turns for each power
    for round_index in range(max_rounds):
        logger.debug(f"DIPLOMACY | Starting round {round_index+1}/{max_rounds}")
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(active_powers)
        ) as executor:
            futures = {}
            for power_name in active_powers:
                model_id = game.power_model_map.get(power_name, "o3-mini")
                client = load_model_client(model_id)
                possible_orders = gather_possible_orders(game, power_name)
                if not possible_orders:
                    logger.info(f"DIPLOMACY | {power_name} | No orderable locations, skipping negotiation")
                    continue
                board_state = game.get_state()

                logger.debug(f"DIPLOMACY | {power_name} | Requesting conversation response from {model_id}")
                future = executor.submit(
                    client.get_conversation_reply,
                    game,
                    board_state,
                    power_name,
                    possible_orders,
                    game_history,
                    game.current_short_phase,
                    active_powers,
                    phase_summaries=game.phase_summaries,
                )

                futures[future] = power_name

            message_count = 0
            for future in concurrent.futures.as_completed(futures):
                power_name = futures[future]
                try:
                    messages = future.result()
                    if messages:
                        logger.debug(f"DIPLOMACY | {power_name} | Generated {len(messages)} messages")
                        for message in messages:
                            recipient = message["recipient"]
                            msg_type = "global" if recipient == GLOBAL else "private"
                            truncated_content = message["content"][:50] + ("..." if len(message["content"]) > 50 else "")
                            
                            logger.debug(f"DIPLOMACY | {power_name} → {recipient} | {msg_type.upper()} | {truncated_content}")
                            
                            # Create an official message in the Diplomacy engine
                            diplo_message = Message(
                                phase=game.current_short_phase,
                                sender=power_name,
                                recipient=message["recipient"],
                                message=message["content"],
                            )
                            game.add_message(diplo_message)
                            game_history.add_message(
                                game.current_short_phase,
                                power_name,
                                message["recipient"],
                                message["content"],
                            )
                            conversation_messages.append(message)
                            message_count += 1
                    else:
                        logger.warning(f"DIPLOMACY | {power_name} | No valid messages generated")
                        model_error_stats[power_name]["conversation_errors"] += 1
                except Exception as exc:
                    error_msg = str(exc)[:150]
                    logger.error(f"DIPLOMACY | {power_name} | Request failed: {error_msg}")
                    model_error_stats[power_name]["conversation_errors"] += 1
        
        logger.debug(f"DIPLOMACY | Round {round_index+1} completed with {message_count} new messages")

    total_messages = len(conversation_messages)
    global_msgs = sum(1 for m in conversation_messages if m["recipient"] == GLOBAL)
    private_msgs = total_messages - global_msgs
    
    logger.info(f"DIPLOMACY | Negotiation complete: {total_messages} messages ({global_msgs} global, {private_msgs} private)")
    return conversation_messages
