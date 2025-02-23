import argparse
import logging
import time
import dotenv
import os
import json
from collections import defaultdict
import concurrent.futures

# Suppress Gemini/PaLM gRPC warnings
os.environ["GRPC_PYTHON_LOG_LEVEL"] = "40"  # ERROR level only

from diplomacy import Game
from diplomacy.utils.export import to_saved_game_format

from ai_diplomacy.clients import load_model_client
from ai_diplomacy.utils import (
    get_valid_orders,
    gather_possible_orders,
    assign_models_to_powers,
)
from ai_diplomacy.negotiations import conduct_negotiations
from ai_diplomacy.game_history import GameHistory

dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)


def my_summary_callback(system_prompt, user_prompt, model_name):
    # Route to the desired model specified by the command-line argument
    client = load_model_client(model_name, emptysystem=True)
    combined_prompt = f"{system_prompt}\n\n{user_prompt}"
    # Pseudo-code for generating a response:
    return client.generate_response(combined_prompt, empty_system=True)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run a Diplomacy game simulation with configurable parameters."
    )
    parser.add_argument(
        "--max_year",
        type=int,
        default=1910,
        help="Maximum year to simulate. The game will stop once this year is reached.",
    )
    parser.add_argument(
        "--summary_model",
        type=str,
        default="o3-mini",
        help="Model name to use for generating phase summaries.",
    )
    parser.add_argument(
        "--num_negotiation_rounds",
        type=int,
        default=5,
        help="Number of negotiation rounds per phase.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output filename for the final JSON result. If not provided, a timestamped name will be generated.",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="",
        help=(
            "Comma-separated list of model names to assign to powers in order. "
            "The order is: AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY."
        ),
    )
    return parser.parse_args()


def save_game_state(game, result_folder, game_file_path, model_error_stats, args, is_final=False):
    """
    Save the current game state and related information
    
    Args:
        game: The diplomacy game instance
        result_folder: Path to the results folder
        game_file_path: Base path for the game file
        model_error_stats: Dictionary containing model error statistics
        args: Command line arguments
        is_final: Boolean indicating if this is the final save
    """
    # Generate unique filename for periodic saves
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    if not is_final:
        output_path = f"{game_file_path}_checkpoint_{timestamp}.json"
    else:
        output_path = game_file_path
        # If final file exists, append timestamp
        if os.path.exists(output_path):
            logger.info("Game file already exists, saving with unique filename.")
            output_path = f"{output_path}_{timestamp}.json"
    
    # Save game state
    to_saved_game_format(game, output_path=output_path)
    
    # Save overview data
    overview_file_path = f"{result_folder}/overview.jsonl"
    with open(overview_file_path, "w") as overview_file:
        overview_file.write(json.dumps(model_error_stats) + "\n")
        overview_file.write(json.dumps(game.power_model_map) + "\n")
        overview_file.write(json.dumps(vars(args)) + "\n")
    
    logger.info(f"Saved game checkpoint to: {output_path}")


def main():
    args = parse_arguments()
    max_year = args.max_year
    summary_model = args.summary_model

    logger.info("Starting a new Diplomacy game for testing with multiple LLMs, now concurrent!")
    start_whole = time.time()

    model_error_stats = defaultdict(
        lambda: {"conversation_errors": 0, "order_decoding_errors": 0}
    )

    # Create a fresh Diplomacy game
    game = Game()
    game_history = GameHistory()

    # Ensure game has phase_summaries attribute
    if not hasattr(game, "phase_summaries"):
        game.phase_summaries = {}

    # Determine the result folder based on a timestamp
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    result_folder = f"./results/{timestamp_str}"
    os.makedirs(result_folder, exist_ok=True)

    # ---------------------------
    # ADD FILE HANDLER FOR LOGS
    # ---------------------------
    log_file_path = os.path.join(result_folder, "game.log")
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(file_handler)
    logger.info(f"File handler added. Writing logs to {log_file_path}.")

    # File paths
    manifesto_path = f"{result_folder}/game_manifesto.txt"
    # Use provided output filename or generate one based on the timestamp
    game_file_path = args.output if args.output else f"{result_folder}/lmvsgame.json"
    overview_file_path = f"{result_folder}/overview.jsonl"

    # Handle power model mapping
    if args.models:
        # Expected order: AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY
        powers_order = [
            "AUSTRIA",
            "ENGLAND",
            "FRANCE",
            "GERMANY",
            "ITALY",
            "RUSSIA",
            "TURKEY",
        ]
        provided_models = [name.strip() for name in args.models.split(",")]
        if len(provided_models) != len(powers_order):
            logger.error(
                f"Expected {len(powers_order)} models for --power-models but got {len(provided_models)}. Exiting."
            )
            return
        game.power_model_map = dict(zip(powers_order, provided_models))
    else:
        game.power_model_map = assign_models_to_powers(randomize=True)

    logger.debug("Power model assignments:")
    for power, model_id in game.power_model_map.items():
        logger.debug(f"{power} => type={type(model_id)}, value={model_id}")

    # Also, if you prefer to fix the negotiation function:
    # We could do a one-liner ensuring all model_id are strings:
    for p in game.power_model_map:
        if not isinstance(game.power_model_map[p], str):
            game.power_model_map[p] = str(game.power_model_map[p])

    logger.info("Post-cleanup: Verified all power model IDs are strings.")

    round_counter = 0  # Track number of rounds

    while not game.is_game_done:
        phase_start = time.time()
        current_phase = game.get_current_phase()
        logger.info(
            f"PHASE: {current_phase} (time so far: {phase_start - start_whole:.2f}s)"
        )

        # DEBUG: Print the short phase to confirm
        logger.info(f"INFO: The current short phase is '{game.current_short_phase}'")

        # Prevent unbounded simulation based on year
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"Reached year {year_int}, stopping the test game early.")
            break

        # If it's a movement phase (e.g. ends with "M"), conduct negotiations
        if game.current_short_phase.endswith("M"):
            logger.info("Starting negotiation phase block...")
            conversation_messages = conduct_negotiations(
                game,
                game_history,
                model_error_stats,
                max_rounds=args.num_negotiation_rounds,
            )
        else:
            conversation_messages = []

        # Gather orders from each power concurrently
        active_powers = [
            (p_name, p_obj)
            for p_name, p_obj in game.powers.items()
            if not p_obj.is_eliminated()
        ]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(active_powers)
        ) as executor:
            futures = {}
            for power_name, _ in active_powers:
                model_id = game.power_model_map.get(power_name, "o3-mini")
                client = load_model_client(model_id, power_name=power_name)
                possible_orders = gather_possible_orders(game, power_name)
                if not possible_orders:
                    logger.info(f"No orderable locations for {power_name}; skipping.")
                    continue
                board_state = game.get_state()

                future = executor.submit(
                    get_valid_orders,
                    game,
                    client,
                    board_state,
                    power_name,
                    possible_orders,
                    game_history,
                    game.phase_summaries,
                    model_error_stats,
                )
                futures[future] = power_name
                logger.debug(f"Submitted get_valid_orders task for {power_name}.")

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
        # Pass the summary model to the callback via a lambda function
        phase_data = game.process(
            phase_summary_callback=lambda sys, usr: my_summary_callback(
                sys, usr, summary_model
            )
        )
        # Add orders to game history
        for power_name in game.order_history[current_phase]:
            orders = game.order_history[current_phase][power_name]
            results = []
            for order in orders:
                # Example move: "A PAR H" -> unit="A PAR", order_part="H"
                tokens = order.split(" ", 2)
                if len(tokens) < 3:
                    continue
                unit = " ".join(tokens[:2])  # e.g. "A PAR"
                order_part = tokens[2]  # e.g. "H" or "S A MAR"
                results.append(
                    [str(x) for x in game.result_history[current_phase][unit]]
                )
            game_history.add_orders(
                current_phase,
                power_name,
                game.order_history[current_phase][power_name],
                results,
            )
        logger.info("Phase complete.\n")

        # Retrieve and log the summary of the phase
        summary_text = phase_data.summary or "(No summary found.)"
        border = "=" * 80
        logger.info(
            f"{border}\nPHASE SUMMARY for {phase_data.name}:\n{summary_text}\n{border}"
        )

        # Append the summary to the manifesto file
        with open(manifesto_path, "a") as f:
            f.write(f"=== {phase_data.name} ===\n{summary_text}\n\n")

        # Increment round counter after processing each phase
        round_counter += 1
        
        # Save every 5 rounds
        if round_counter % 5 == 0:
            logger.info(f"Saving checkpoint after round {round_counter}...")
            save_game_state(game, result_folder, game_file_path, model_error_stats, args, is_final=False)

        # Check if we've exceeded the max year
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"Reached year {year_int}, stopping the test game early.")
            break

    # Save final result
    duration = time.time() - start_whole
    logger.info(f"Game ended after {duration:.2f}s. Saving final state...")
    
    save_game_state(game, result_folder, game_file_path, model_error_stats, args, is_final=True)
    
    logger.info(f"Saved game data, manifesto, and error stats in: {result_folder}")
    logger.info("Done.")


if __name__ == "__main__":
    main()
