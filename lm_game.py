import logging
import time
import dotenv
import os
import re
import json

# Suppress Gemini/PaLM gRPC warnings
os.environ['GRPC_PYTHON_LOG_LEVEL'] = '40'  # ERROR level only
import google.generativeai as genai  # Import after setting log level

from diplomacy import Game
from diplomacy.utils.export import to_saved_game_format

# Added import: we'll create and add standard Diplomacy messages
from diplomacy.engine.message import Message, GLOBAL

# For concurrency:
import concurrent.futures

from lm_service_versus import load_model_client, assign_models_to_powers

dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S"
)

def gather_possible_orders(game, power_name):
    """
    Returns a dictionary mapping each orderable location to the list of valid orders.
    """
    orderable_locs = game.get_orderable_locations(power_name)
    all_possible = game.get_all_possible_orders()

    result = {}
    for loc in orderable_locs:
        result[loc] = all_possible.get(loc, [])
    return result

def conduct_negotiations(game, max_rounds=3):
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
    for round_index in range(max_rounds):
        for power_name in active_powers:
            # Build the conversation context from all messages the power can see
            visible_messages = []
            for msg in conversation_messages:
                # Include if message is global or if power is sender/recipient
                if msg['recipient'] == GLOBAL or msg['sender'] == power_name or msg['recipient'] == power_name:
                    visible_messages.append(
                        f"{msg['sender']} to {msg['recipient']}: {msg['content']}"
                    )
            
            conversation_so_far = "\n".join(visible_messages)

            # Add few-shot example for message format
            few_shot_example = """
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
"""

            # Ask the LLM for a single reply
            client = load_model_client(game.power_model_map.get(power_name, "o3-mini"))
            new_message = client.get_conversation_reply(
                power_name=power_name,
                conversation_so_far=conversation_so_far + "\n" + few_shot_example,
                game_phase=game.current_short_phase,
                phase_summaries=game.phase_summaries
            )

            if new_message:
                try:
                    # Parse the JSON response
                    # Find the JSON block between curly braces
                    json_match = re.search(r'\{[^}]+\}', new_message)
                    if json_match:
                        message_data = json.loads(json_match.group(0))
                        
                        # Extract message details
                        message_type = message_data.get('message_type', 'global')
                        content = message_data.get('content', '').strip()
                        recipient = message_data.get('recipient', GLOBAL)
                        
                        # Validate recipient if private message
                        if message_type == 'private' and recipient not in active_powers:
                            logger.warning(f"Invalid recipient {recipient} for private message, defaulting to GLOBAL")
                            recipient = GLOBAL
                        
                        # For private messages, ensure recipient is specified
                        if message_type == 'private' and recipient == GLOBAL:
                            logger.warning("Private message without recipient specified, defaulting to GLOBAL")
                            
                        # Log for debugging
                        logger.info(f"Power {power_name} sends {message_type} message to {recipient}")
                        
                        # Keep local record for building future conversation context
                        conversation_messages.append({
                            "sender": power_name,
                            "recipient": recipient,
                            "content": content
                        })

                        # Create an official message in the Diplomacy engine
                        diplo_message = Message(
                            phase=game.current_short_phase,
                            sender=power_name,
                            recipient=recipient,
                            message=content
                        )
                        game.add_message(diplo_message)


                except (json.JSONDecodeError, AttributeError) as e:
                    logger.error(f"Failed to parse message from {power_name}: {e}")
                    continue
    logger.info("Negotiation phase complete.")
    return conversation_messages

def my_summary_callback(system_prompt, user_prompt):
    # e.g., route to your desired model:
    client = load_model_client("o3-mini")
    combined_prompt = f"{system_prompt}\n\n{user_prompt}"
    # Pseudo-code for generating a response:
    return client.generate_response(combined_prompt)

def main():
    logger.info("Starting a new Diplomacy game for testing with multiple LLMs, now concurrent!")
    start_whole = time.time()

    # Create a fresh Diplomacy game
    game = Game()
    # Ensure game has phase_summaries = {}
    if not hasattr(game, 'phase_summaries'):
        game.phase_summaries = {}

    # Map each power to its chosen LLM
    game.power_model_map = assign_models_to_powers()

    max_year = 1902

    while not game.is_game_done:
        phase_start = time.time()
        current_phase = game.get_current_phase()
        logger.info(f"PHASE: {current_phase} (time so far: {phase_start - start_whole:.2f}s)")

        # DEBUG: Print the short phase to confirm
        logger.info(f"DEBUG: current_short_phase is '{game.current_short_phase}'")

        # Prevent unbounded sim
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"Reached year {year_int}, stopping the test game early.")
            break

        # Use endswith("M") for movement phases (like F1901M, S1902M)
        if game.current_short_phase.endswith("M"):
            logger.info("Starting negotiation phase block...")
            conversation_messages = conduct_negotiations(game, max_rounds=3)

        # Convert conversation_messages to single string for orders
        conversation_text_for_orders = "\n".join([
            f"{msg['sender']} to {msg['recipient']}: {msg['content']}"
            for msg in conversation_messages
        ])

        # Gather orders from each power concurrently
        active_powers = [
            (p_name, p_obj) for p_name, p_obj in game.powers.items()
            if not p_obj.is_eliminated()
        ]

        # Then proceed with concurrent order generation
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active_powers)) as executor:
            futures = {}
            for power_name, _ in active_powers:
                model_id = game.power_model_map.get(power_name, "o3-mini")
                client = load_model_client(model_id)
                possible_orders = gather_possible_orders(game, power_name)
                if not possible_orders:
                    logger.info(f"No orderable locations for {power_name}; skipping.")
                    continue
                board_state = game.get_state()
                future = executor.submit(
                    client.get_orders, 
                    board_state, 
                    power_name, 
                    possible_orders, 
                    conversation_text_for_orders,
                    game.phase_summaries
                )
                futures[future] = power_name
                logger.debug(f"Submitted get_orders task for power {power_name}.")

            for future in concurrent.futures.as_completed(futures):
                p_name = futures[future]
                try:
                    orders = future.result()
                    logger.debug(f"Orders for {p_name}: {orders}")
                    if orders:
                        game.set_orders(p_name, orders)
                        logger.debug(f"Set orders for {p_name} in {game.current_short_phase}: {orders}")
                    else:
                        logger.debug(f"No orders returned for {p_name}.")
                except Exception as exc:
                    logger.error(f"LLM request failed for {p_name}: {exc}")

        logger.info("Processing orders...\n")
        phase_data = game.process(phase_summary_callback=my_summary_callback)
        logger.info("Phase complete.\n")

        # Retrieve the last-processed phase data from the game's history
        summary_text = phase_data.summary or "(No summary found.)"

        # Print in pretty ASCII format
        border = "=" * 80
        logger.info(f"{border}\nPHASE SUMMARY for {phase_data.name}:\n{summary_text}\n{border}")

        # Optionally append it to the same text file, so we keep a log
        with open("game_manifesto.txt", "a") as f:
            f.write(f"=== {phase_data.name} ===\n{summary_text}\n\n")

        # End-of-loop checks
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"Reached year {year_int}, stopping the test game early.")
            break

    # Save final result
    duration = time.time() - start_whole
    logger.info(f"Game ended after {duration:.2f}s. Saving to 'lmvsgame.json'.")
    # Save the game to a JSON file
    output_path = 'lmvsgame.json'
    if not os.path.exists(output_path):
        to_saved_game_format(game, output_path=output_path)
    else:
        logger.info("Game file already exists, saving with unique filename.")
        output_path = f'{output_path}_{time.strftime("%Y%m%d_%H%M%S")}.json'
        to_saved_game_format(game, output_path=output_path)

if __name__ == "__main__":
    main()