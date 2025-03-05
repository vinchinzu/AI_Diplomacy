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

from ai_diplomacy.model_loader import load_model_client
from ai_diplomacy.utils import (
    get_valid_orders,
    gather_possible_orders,
    assign_models_to_powers,
)
from ai_diplomacy.negotiations import conduct_negotiations
from ai_diplomacy.planning import planning_phase
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.long_story_short import configure_context_manager
from ai_diplomacy.clients import configure_logging

dotenv.load_dotenv()

# Configure logger with a consistent format
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

# Configure specific loggers to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# Ensure our application loggers are at appropriate levels
logging.getLogger("client").setLevel(logging.INFO)
logging.getLogger("ai_diplomacy").setLevel(logging.INFO)



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
    parser.add_argument(
        "--planning_phase", 
        action="store_true",
        help="Enable the planning phase for each power to set strategic directives.",
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
            logger.info("STORAGE | Final game file already exists, saving with unique timestamp")
            output_path = f"{output_path}_{timestamp}.json"
    
    # Save game state
    to_saved_game_format(game, output_path=output_path)
    
    # Save overview data
    overview_file_path = f"{result_folder}/overview.jsonl"
    with open(overview_file_path, "w") as overview_file:
        overview_file.write(json.dumps(model_error_stats) + "\n")
        overview_file.write(json.dumps(game.power_model_map) + "\n")
        overview_file.write(json.dumps(vars(args)) + "\n")
    
    logger.info(f"STORAGE | Game checkpoint saved to: {output_path}")


def main():
    args = parse_arguments()
    
    # Configure logging
    log_level = getattr(logging, args.log_level)
    configure_logging(
        log_full_prompts=args.log_full_prompts,
        log_full_responses=args.log_full_responses,
        suppress_connection_logs=not args.verbose,
        log_level=log_level
    )
    
    # Configure the context manager with the same summary model
    configure_context_manager(
        phase_threshold=15000,
        message_threshold=15000,
        summary_model=args.summary_model
    )
    max_year = args.max_year

    logger.info("GAME_START | Initializing Diplomacy game with multiple LLM agents")
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
    file_handler.setLevel(logging.DEBUG)  # Ensure we capture all levels in the file
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s", datefmt="%H:%M:%S")
    )
    
    # Add the handler to root logger to capture all modules' logs
    logging.getLogger().addHandler(file_handler)
    
    # Also add to specific loggers we care about most for summarization
    logging.getLogger("ai_diplomacy.long_story_short").addHandler(file_handler)
    logging.getLogger("ai_diplomacy.long_story_short").setLevel(logging.DEBUG)
    
    logger.info(f"LOGGING | File handler configured to write logs to {log_file_path}")
    logger.info(f"LOGGING | Capturing detailed context management logs at DEBUG level")

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
                f"CONFIG_ERROR | Expected {len(powers_order)} models in --models argument but got {len(provided_models)}. Exiting."
            )
            return
        game.power_model_map = dict(zip(powers_order, provided_models))
    else:
        game.power_model_map = assign_models_to_powers(randomize=True)

    logger.debug("POWERS | Model assignments:")
    for power, model_id in game.power_model_map.items():
        logger.debug(f"POWERS | {power} assigned to {model_id}")

    # Also, if you prefer to fix the negotiation function:
    # We could do a one-liner ensuring all model_id are strings:
    for p in game.power_model_map:
        if not isinstance(game.power_model_map[p], str):
            game.power_model_map[p] = str(game.power_model_map[p])

    logger.debug("POWERS | Verified all power model IDs are strings")

    round_counter = 0  # Track number of rounds

    while not game.is_game_done:
        phase_start = time.time()
        current_phase = game.get_current_phase()
        logger.info(
            f"PHASE | {current_phase} | Starting (elapsed game time: {phase_start - start_whole:.2f}s)"
        )

        # Get the current short phase
        logger.debug(f"PHASE | Current short phase: '{game.current_short_phase}'")

        # Prevent unbounded simulation based on year
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"GAME_END | Reached year limit ({year_int} > {max_year}), terminating game")
            break

        # If it's a movement phase (e.g. ends with "M"), conduct negotiations
        if game.current_short_phase.endswith("M"):
            if args.planning_phase:
                logger.info("Starting planning phase block...")
                game_history = planning_phase(
                    game,
                    game_history,
                    model_error_stats,
                )
            logger.info("Starting negotiation phase block...")
            game_history = conduct_negotiations(
                game,
                game_history,
                model_error_stats,
                max_rounds=args.num_negotiation_rounds,
            )
        # Gather orders from each power concurrently
        active_powers = [
            (p_name, p_obj)
            for p_name, p_obj in game.powers.items()
            if not p_obj.is_eliminated()
        ]
        
        logger.info(f"ORDERS | {current_phase} | Requesting orders from {len(active_powers)} active powers")

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(active_powers)
        ) as executor:
            futures = {}
            for power_name, _ in active_powers:
                model_id = game.power_model_map.get(power_name, "o3-mini")
                client = load_model_client(model_id, power_name=power_name)
                possible_orders = gather_possible_orders(game, power_name)
                if not possible_orders:
                    logger.info(f"ORDERS | {power_name} | No orderable locations, skipping")
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
                logger.debug(f"ORDERS | {power_name} | Requested orders from {model_id}")

            for future in concurrent.futures.as_completed(futures):
                p_name = futures[future]
                try:
                    orders = future.result()
                    if orders:
                        logger.debug(f"ORDERS | {p_name} | Received {len(orders)} valid orders")
                        game.set_orders(p_name, orders)
                        logger.debug(f"ORDERS | {p_name} | Orders set for {game.current_short_phase}")
                    else:
                        logger.warning(f"ORDERS | {p_name} | No valid orders returned")
                except Exception as exc:
                    logger.error(f"ORDERS | {p_name} | Request failed: {str(exc)[:150]}")
        logger.info("Processing orders...\n")
        game.process()
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
        logger.info(f"PROCESSING | {current_phase} | Phase completed")
        # Append the strategic directives to the manifesto file
        strategic_directives = game_history.get_strategic_directives()
        if strategic_directives:
            out_str = f"Strategic directives for {current_phase}:\n"
            for power, directive in strategic_directives.items():
                out_str += f"{power}: {directive}\n\n"
            out_str += f"------------------------------------------\n"
            with open(manifesto_path, "a") as f:
                f.write(out_str)

        # Check if we've exceeded the max year
        year_str = current_phase[1:5]
        year_int = int(year_str)
        if year_int > max_year:
            logger.info(f"GAME_END | Reached year limit ({year_int} > {max_year}), terminating game")
            break

    # Save final result
    duration = time.time() - start_whole
    logger.info(f"GAME_END | Duration: {duration:.2f}s | Saving final state")
    
    save_game_state(game, result_folder, game_file_path, model_error_stats, args, is_final=True)
    
    logger.info(f"STORAGE | Game data saved in: {result_folder}")
    logger.info("GAME_END | Simulation complete")


if __name__ == "__main__":
    main()
