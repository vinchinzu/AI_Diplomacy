import logging
import time
import dotenv
import os
import json

# Additional import for error stats
from collections import defaultdict

# Suppress Gemini/PaLM gRPC warnings
os.environ["GRPC_PYTHON_LOG_LEVEL"] = "40"  # ERROR level only

from diplomacy import Game
from diplomacy.utils.export import to_saved_game_format

# Added import: we'll create and add standard Diplomacy messages

import concurrent.futures

from ai_diplomacy.clients import load_model_client, assign_models_to_powers
from ai_diplomacy.utils import get_valid_orders_with_retry, gather_possible_orders
from ai_diplomacy.negotiations import conduct_negotiations

dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)


def my_summary_callback(system_prompt, user_prompt):
    # e.g., route to your desired model:
    client = load_model_client("o3-mini")
    combined_prompt = f"{system_prompt}\n\n{user_prompt}"
    # Pseudo-code for generating a response:
    return client.generate_response(combined_prompt)


def main():
    logger.info(
        "Starting a new Diplomacy game for testing with multiple LLMs, now concurrent!"
    )
    start_whole = time.time()

    model_error_stats = defaultdict(
        lambda: {"conversation_errors": 0, "order_decoding_errors": 0}
    )

    # Create a fresh Diplomacy game
    game = Game()
    # Ensure game has phase_summaries = {}
    if not hasattr(game, "phase_summaries"):
        game.phase_summaries = {}

    # For storing results in a unique subfolder
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    result_folder = f"./results/{timestamp_str}"
    if not os.path.exists(result_folder):
        os.makedirs(result_folder)

    # Manifesto and game file paths
    manifesto_path = f"{result_folder}/game_manifesto.txt"
    game_file_path = f"{result_folder}/lmvsgame.json"
    stats_file_path = f"{result_folder}/error_stats.json"

    game.power_model_map = assign_models_to_powers()
    max_year = 1910

    while not game.is_game_done:
        phase_start = time.time()
        current_phase = game.get_current_phase()
        logger.info(
            f"PHASE: {current_phase} (time so far: {phase_start - start_whole:.2f}s)"
        )

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
            conversation_messages = conduct_negotiations(
                game, model_error_stats, max_rounds=10
            )
        else:
            # If we have no conversation_messages in phases that are not Movement (e.g. Retreat/Build)
            conversation_messages = []

        conversation_text_for_orders = "\n".join(
            [
                f"{msg['sender']} to {msg['recipient']}: {msg['content']}"
                for msg in conversation_messages
            ]
        )

        # Gather orders from each power concurrently
        active_powers = [
            (p_name, p_obj)
            for p_name, p_obj in game.powers.items()
            if not p_obj.is_eliminated()
        ]

        # Then proceed with concurrent order generation
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(active_powers)
        ) as executor:
            futures = {}
            for power_name, _ in active_powers:
                model_id = game.power_model_map.get(power_name, "o3-mini")
                client = load_model_client(model_id)
                possible_orders = gather_possible_orders(game, power_name)
                if not possible_orders:
                    logger.info(f"No orderable locations for {power_name}; skipping.")
                    continue
                board_state = game.get_state()

                # Submit a task that includes up to 3 attempts at valid orders
                future = executor.submit(
                    get_valid_orders_with_retry,
                    game,
                    client,
                    board_state,
                    power_name,
                    possible_orders,
                    conversation_text_for_orders,  # existing conversation text
                    game.phase_summaries,
                    model_error_stats,
                    3,  # max_retries
                )
                futures[future] = power_name
                logger.debug(
                    f"Submitted get_valid_orders_with_retry task for {power_name}."
                )

            for future in concurrent.futures.as_completed(futures):
                p_name = futures[future]
                try:
                    orders = future.result()
                    logger.debug(f"Validated orders for {p_name}: {orders}")
                    if orders:
                        game.set_orders(p_name, orders)
                        logger.debug(
                            f"Set orders for {p_name} in {game.current_short_phase}: {orders}"
                        )
                    else:
                        logger.debug(f"No valid orders returned for {p_name}.")
                except Exception as exc:
                    logger.error(f"LLM request failed for {p_name}: {exc}")

        logger.info("Processing orders...\n")
        phase_data = game.process(phase_summary_callback=my_summary_callback)
        logger.info("Phase complete.\n")

        # Retrieve the last-processed phase data from the game's history
        summary_text = phase_data.summary or "(No summary found.)"

        # Print in pretty ASCII format
        border = "=" * 80
        logger.info(
            f"{border}\nPHASE SUMMARY for {phase_data.name}:\n{summary_text}\n{border}"
        )

        # Write to unique game_manifesto in the timestamped folder
        with open(manifesto_path, "a") as f:
            f.write(f"=== {phase_data.name} ===\n{summary_text}\n\n")

        # End-of-loop checks
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"Reached year {year_int}, stopping the test game early.")
            break

    # Save final result
    duration = time.time() - start_whole
    logger.info(f"Game ended after {duration:.2f}s. Saving to final JSON...")

    # Save final result to the unique subfolder
    output_path = game_file_path
    if not os.path.exists(output_path):
        to_saved_game_format(game, output_path=output_path)
    else:
        logger.info("Game file already exists, saving with unique filename.")
        output_path = f"{output_path}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        to_saved_game_format(game, output_path=output_path)

    # Dump our error stats to JSON

    with open(stats_file_path, "w") as stats_f:
        json.dump(model_error_stats, stats_f, indent=2)

    logger.info(f"Saved game data, manifesto, and error stats in: {result_folder}")
    logger.info("Done.")


if __name__ == "__main__":
    main()
