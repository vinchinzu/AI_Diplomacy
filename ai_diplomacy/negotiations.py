from dotenv import load_dotenv
import logging

from diplomacy.engine.message import Message, GLOBAL

from .clients import load_model_client
from .utils import gather_possible_orders

logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

load_dotenv()


def conduct_negotiations(game, conversation_history, model_error_stats, max_rounds=10):
    """
    Conducts a round-robin conversation among all non-eliminated powers.
    Each power can send up to 'max_rounds' messages, choosing between private
    and global messages each turn.
    """
    logger.info("Starting negotiation phase.")

    # Conversation messages are kept in a local list ONLY to build conversation_so_far text.
    conversation_messages = []

    active_powers = [
        p_name for p_name, p_obj in game.powers.items() if not p_obj.is_eliminated()
    ]

    # We do up to 'max_rounds' single-message turns for each power
    for round_index in range(1):
        for power_name in active_powers:
            # # Build the conversation context from all messages the power can see
            # visible_messages = []
            # for msg in conversation_messages:
            #     # Include if message is global or if power is sender/recipient
            #     if (
            #         msg["recipient"] == GLOBAL
            #         or msg["sender"] == power_name
            #         or msg["recipient"] == power_name
            #     ):
            #         visible_messages.append(
            #             f"{msg['sender']} to {msg['recipient']}: {msg['content']}"
            #         )

            # conversation_so_far = "\n".join(visible_messages)
            model_id = game.power_model_map.get(power_name, "o3-mini")
            client = load_model_client(model_id)
            possible_orders = gather_possible_orders(game, power_name)
            if not possible_orders:
                logger.info(f"No orderable locations for {power_name}; skipping.")
                continue
            board_state = game.get_state()

            # Ask the LLM for a single reply
            client = load_model_client(game.power_model_map.get(power_name, "o3-mini"))
            message = client.get_conversation_reply(
                game=game,
                board_state=board_state,
                power_name=power_name,
                possible_orders=possible_orders,
                conversation_history=conversation_history,
                game_phase=game.current_short_phase,
                phase_summaries=game.phase_summaries,
                active_powers=active_powers,
            )

            if message:
                # Create an official message in the Diplomacy engine
                diplo_message = Message(
                    phase=game.current_short_phase,
                    sender=power_name,
                    recipient=message["recipient"],
                    message=message["content"],
                )
                game.add_message(diplo_message)
                conversation_history.add_message(
                    game.current_short_phase, power_name, message
                )
                conversation_messages.append(message)
            else:
                logger.info(f"{power_name} did not send a message.")
                model_error_stats[power_name]["conversation_errors"] += 1

    logger.info("Negotiation phase complete.")
    return conversation_messages
