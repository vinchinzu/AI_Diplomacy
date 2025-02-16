from dotenv import load_dotenv
import logging
import json
import re

from diplomacy.engine.message import Message, GLOBAL

from .clients import load_model_client

logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

load_dotenv()


FEW_SHOT_EXAMPLE = """
Example response formats:
1. For a global message:
{
    "message_type": "global",
    "content": "I propose we all work together against Turkey."
}

2. For a private message:
{
    "message_type": "private",
    "recipient": "FRANCE",
    "content": "Let's form a secret alliance against Germany."
}

Note: There are a total of 10 messages in this negotiation phase. This is message #{} out of 10. By the end, you should have coordinated moves effectively to avoid being blocked or bounced with others.
If you have your plan already figured out, you can just send a public '.' to indicate you're ready to move on.
"""


def conduct_negotiations(game, model_error_stats, max_rounds=10):
    """
    Conducts a round-robin conversation among all non-eliminated powers.
    Each power can send up to 'max_rounds' messages, choosing between private
    and global messages each turn.
    """
    logger.info("Starting negotiation phase.")

    # Conversation messages are kept in a local list ONLY to build conversation_so_far text.
    conversation_messages = []
    return conversation_messages

    active_powers = [
        p_name for p_name, p_obj in game.powers.items() if not p_obj.is_eliminated()
    ]

    # We do up to 'max_rounds' single-message turns for each power
    for round_index in range(max_rounds):
        for power_name in active_powers:
            # Build the conversation context from all messages the power can see
            visible_messages = []
            for msg in conversation_messages:
                # Include if message is global or if power is sender/recipient
                if (
                    msg["recipient"] == GLOBAL
                    or msg["sender"] == power_name
                    or msg["recipient"] == power_name
                ):
                    visible_messages.append(
                        f"{msg['sender']} to {msg['recipient']}: {msg['content']}"
                    )

            conversation_so_far = "\n".join(visible_messages)

            # Ask the LLM for a single reply
            client = load_model_client(game.power_model_map.get(power_name, "o3-mini"))
            new_message = client.get_conversation_reply(
                power_name=power_name,
                conversation_so_far=conversation_so_far + "\n" + FEW_SHOT_EXAMPLE,
                game_phase=game.current_short_phase,
                phase_summaries=game.phase_summaries,
            )

            if new_message:
                try:
                    # Parse the JSON response
                    # Find the JSON block between curly braces
                    json_match = re.search(r"\{[^}]+\}", new_message)
                    if json_match:
                        message_data = json.loads(json_match.group(0))

                        # Extract message details
                        message_type = message_data.get("message_type", "global")
                        content = message_data.get("content", "").strip()
                        recipient = message_data.get("recipient", GLOBAL)

                        # Validate recipient if private message
                        if message_type == "private" and recipient not in active_powers:
                            logger.warning(
                                f"Invalid recipient {recipient} for private message, defaulting to GLOBAL"
                            )
                            recipient = GLOBAL

                        # For private messages, ensure recipient is specified
                        if message_type == "private" and recipient == GLOBAL:
                            logger.warning(
                                "Private message without recipient specified, defaulting to GLOBAL"
                            )

                        # Log for debugging
                        logger.info(
                            f"Power {power_name} sends {message_type} message to {recipient}"
                        )

                        # Keep local record for building future conversation context
                        conversation_messages.append(
                            {
                                "sender": power_name,
                                "recipient": recipient,
                                "content": content,
                            }
                        )

                        # Create an official message in the Diplomacy engine
                        diplo_message = Message(
                            phase=game.current_short_phase,
                            sender=power_name,
                            recipient=recipient,
                            message=content,
                        )
                        game.add_message(diplo_message)

                except (json.JSONDecodeError, AttributeError) as e:
                    logger.error(f"Failed to parse message from {power_name}: {e}")
                    # Increment conversation parse error
                    model_error_stats[power_name]["conversation_errors"] += 1
                    continue

    logger.info("Negotiation phase complete.")
    return conversation_messages
