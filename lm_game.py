import argparse
import asyncio
import logging
import os
import sys # For sys.exit
import time # For basic timing if needed outside of specific logs
import traceback # For exception logging
from typing import Optional # Removed Set

import dotenv
from diplomacy import Game
# Removed: GLOBAL, Message from diplomacy.engine.message (not used directly in new main)
# Removed: to_saved_game_format (handled by GameResultsProcessor)
# Removed: llm (direct use of llm library is now in coordinator)
# Removed: defaultdict, concurrent.futures (orchestrator uses asyncio.gather)

# New refactored components
from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager
# PhaseSummaryGenerator is used by GamePhaseOrchestrator, not directly in main
# from ai_diplomacy.phase_summary import PhaseSummaryGenerator 
from ai_diplomacy.game_orchestrator import GamePhaseOrchestrator
from ai_diplomacy.game_results import GameResultsProcessor
from ai_diplomacy.game_history import GameHistory
# DiplomacyAgent and AgentLLMInterface are primarily managed by AgentManager
# from ai_diplomacy.agent import DiplomacyAgent 
# from ai_diplomacy.llm_interface import AgentLLMInterface

# get_valid_orders is kept from the original utils.py / lm_game.py for now.
# gather_possible_orders might still be needed by get_valid_orders or other utils.
from ai_diplomacy.utils import get_valid_orders # Removed gather_possible_orders

# Removed old direct imports of assign_models_to_powers, conduct_negotiations, planning_phase,
# initialize_agent_state_ext, narrative related imports as these functionalities
# are now part of the new classes or deprecated in this simplified entry point.

# Suppress Gemini/PaLM gRPC warnings if still relevant (can be moved to logging_setup or utils if general)
os.environ["GRPC_PYTHON_LOG_LEVEL"] = "40"
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["ABSL_MIN_LOG_LEVEL"] = "2"
os.environ["GRPC_POLL_STRATEGY"] = "poll"

dotenv.load_dotenv()

# Logger will be configured by setup_logging
logger = logging.getLogger(__name__)

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Diplomacy game simulation with configurable parameters."
    )
    # Arguments from original lm_game.py relevant to GameConfig
    parser.add_argument(
        "--power_name", type=str, default=None, 
        help="Name of the primary power to control (e.g., FRANCE). Optional."
    )
    parser.add_argument(
        "--model_id", type=str, default=None,
        help="Model ID for the primary power's LLM (e.g., ollama/llama3, gpt-4o). Optional."
    )
    parser.add_argument(
        "--num_players", type=int, default=7, 
        help="Number of LLM-controlled players. Default: 7."
    )
    parser.add_argument(
        "--game_id_prefix", type=str, default="diplomacy_game",
        help="Prefix for the game ID if not explicitly set. Default: 'diplomacy_game'."
    )
    parser.add_argument(
        "--game_id", type=str, default=None,
        help="Specific game ID to use. If None, one will be generated. Default: None."
    )
    parser.add_argument(
        "--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level. Default: INFO."
    )
    parser.add_argument(
        "--log_to_file", type=lambda x: (str(x).lower() == 'true'), default=True,
        help="Enable/disable file logging. Default: True."
    )
    parser.add_argument(
        "--log_dir", type=str, default=None, # GameConfig handles default base if this is None
        help="Base directory for logs. Game-specific subfolder will be created here. Default: './logs'."
    )
    parser.add_argument(
        "--perform_planning_phase", action="store_true", default=False,
        help="Enable the planning phase for each power. Default: False."
    )
    parser.add_argument(
        "--num_negotiation_rounds", type=int, default=3, # Original default was 0, updated to common use
        help="Number of negotiation rounds per movement phase. Default: 3."
    )
    parser.add_argument(
        "--negotiation_style", type=str, default="simultaneous", choices=["simultaneous", "round-robin"],
        help="Style of negotiation rounds. Default: 'simultaneous'."
    )
    parser.add_argument(
        "--fixed_models", type=str, default=None,
        help="Comma-separated list of model IDs to assign to powers (e.g., 'gpt-4o,ollama/llama3'). Cycles if fewer than num_players."
    )
    parser.add_argument(
        "--randomize_fixed_models", action="store_true", default=False,
        help="Randomize assignment of fixed_models to powers. Default: False."
    )
    parser.add_argument(
        "--exclude_powers", type=str, default=None,
        help="Comma-separated list of powers to exclude from LLM control (e.g., 'TURKEY,RUSSIA')."
    )
    parser.add_argument(
        "--max_years", type=int, default=None, # Original was 1901, now optional
        help="Maximum game year to simulate. Game ends after this year's Winter phase. Default: No limit."
    )
    # --output argument from original is implicitly handled by log_dir/game_id structure in GameConfig for results.
    # If a specific single output file for game JSON is still needed, it can be added.
    # For now, results are saved in results_dir within the game_id_specific_log_dir.
    
    # Argument from original args.models, now more clearly named fixed_models
    # Acknowledging --models was for full power assignment, fixed_models is slightly different.
    # If the exact old --models behavior is needed, GameConfig/AgentManager logic might need adjustment.
    # For now, assuming --fixed_models covers the main use case for specifying non-primary models.

    return parser.parse_args()

# get_valid_orders is kept from original utils.py / lm_game.py for now.
# Its own LLM logic is not being refactored in *this* specific step.
# It will be passed to the GamePhaseOrchestrator.
# Signature: async def get_valid_orders(current_game, model_id, agent_system_prompt, board_state, power_name, possible_orders, game_history, model_error_stats, agent_goals, agent_relationships, agent_private_diary_str, log_file_path, phase)
# Note: model_error_stats is removed from its call signature as it's no longer passed down from here.
# get_valid_orders will need to be adapted if it still expects it, or if error stats are handled differently.
# For now, we assume get_valid_orders will be adapted or the parameter can be defaulted to None.

async def main():
    args = parse_arguments()
    
    # 1. Initialize GameConfig
    # GameConfig now handles deriving log paths, game_id etc.
    # It also converts args.fixed_models and args.exclude_powers from CSV strings to lists.
    if args.fixed_models:
        # Remove spaces after commas for robustness
        args.fixed_models = [m.strip() for m in args.fixed_models.replace(' ', '').split(',')]
    if args.exclude_powers:
        args.exclude_powers = [p.strip().upper() for p in args.exclude_powers.split(',')]
        
    config = GameConfig(args)

    # 2. Setup Logging (uses GameConfig)
    setup_logging(config) # Configures root logger, console, and optional file handler

    logger.info(f"Starting Diplomacy game: {config.game_id}")
    logger.info(f"Full configuration: {vars(config.args)}") # Log all parsed args
    start_time = time.time()

    game: Optional[Game] = None # Initialize game to None for finally block
    game_history: Optional[GameHistory] = None # Initialize for finally block
    agent_manager: Optional[AgentManager] = None # Initialize for finally block

    try:
        # 3. Create Game Instance
        game = Game()
        game_history = GameHistory()
        # Store game instance in config for access by other components if needed (orchestrator does this)

        # 4. Initialize AgentManager (uses GameConfig)
        agent_manager = AgentManager(config)

        # 5. Assign models and Initialize Agents
        # Use all powers from the game instance for assignment.
        all_game_powers = list(game.powers.keys())
        powers_and_models_map = agent_manager.assign_models(all_game_powers)
        
        if not powers_and_models_map:
            logger.error("No LLM-controlled powers were assigned. Exiting.")
            sys.exit(1) # Exit if no agents to run
            
        agent_manager.initialize_agents(powers_and_models_map)
        
        if not agent_manager.agents:
            logger.error("Failed to initialize any agents. Exiting.")
            # This might happen if all agent creations failed.
            sys.exit(1)

        # 6. Initialize GamePhaseOrchestrator
        # PhaseSummaryGenerator is now created on-the-fly by the orchestrator.
        orchestrator = GamePhaseOrchestrator(
            game_config=config, # type: ignore
            agent_manager=agent_manager,
            # Removed phase_summary_generator=None, as it's no longer an __init__ param
            get_valid_orders_func=get_valid_orders # Pass the existing function
        )

        # 7. Run Game Loop
        await orchestrator.run_game_loop(game, game_history)

    except KeyboardInterrupt:
        logger.info("Game interrupted by user (KeyboardInterrupt). Saving partial results...")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the game: {e}", exc_info=True)
        # Ensure traceback is logged if not already by default logger settings
        detailed_error = traceback.format_exc()
        logger.error(f"Detailed traceback:\n{detailed_error}")
    finally:
        # 8. Process and Save Results
        if game and game_history and agent_manager: # Ensure game object and history exist
            logger.info("Game loop finished or interrupted. Processing final results...")
            results_processor = GameResultsProcessor(config)
            results_processor.log_final_results(game)
            if config.log_to_file:
                results_processor.save_game_state(game, game_history) 
                if agent_manager.agents: # Check if agents were initialized
                    results_processor.save_agent_manifestos(agent_manager.agents)
                else:
                    logger.warning("AgentManager agents not initialized, skipping manifesto saving.")
            logger.info(f"Results processing complete. Total game time: {time.time() - start_time:.2f} seconds.")
            logger.info(f"Output files are located in: {config.game_id_specific_log_dir}")
        else:
            logger.error("Game object, game history, or agent manager was not initialized. No results to save.")

        logger.info("Diplomacy game simulation ended.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # Catch-all for top-level errors not caught in main's try-except
        # This is important if main() itself raises an error before its own try-block
        # or if asyncio.run() fails for some reason.
        initial_logger = logging.getLogger(__name__) # Use a basic logger if setup_logging failed
        initial_logger.error(f"Critical error in asyncio.run(main()): {e}", exc_info=True)
        detailed_traceback = traceback.format_exc()
        initial_logger.error(f"Detailed traceback:\n{detailed_traceback}")
        sys.exit(1) # Exit with an error code
