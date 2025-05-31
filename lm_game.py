import argparse
import asyncio
import logging
import os
import sys  # For sys.exit
import importlib # For dynamically importing game factory

# Ensure the project root (directory of this script) is in sys.path
# This helps in resolving local package imports like 'ai_diplomacy.something'
_project_root_dir = os.path.dirname(os.path.abspath(__file__))
if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

import time  # For basic timing if needed outside of specific logs
import traceback  # For exception logging
from typing import Optional, Callable, Any, List, Dict # Added Callable, Any, List, Dict

import dotenv
from diplomacy import Game

from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager

#TODO find new one:
from ai_diplomacy.orchestrators.phase_orchestrator import PhaseOrchestrator

from ai_diplomacy.game_results import GameResultsProcessor
from ai_diplomacy.game_history import GameHistory

from ai_diplomacy.general_utils import get_valid_orders  # Removed gather_possible_orders

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


# --- Helper for presets ----------------------------------------------------
def _apply_preset_to_args(args: argparse.Namespace) -> None:
    """
    Map a high‑level preset name to the right combination of flags.
    Does **not** override a value the user already supplied explicitly.
    """
    if not getattr(args, "preset", None):
        return

    if args.preset == "2p_quick":
        args.num_players = args.num_players if args.num_players is not None else 2
        args.num_negotiation_rounds = args.num_negotiation_rounds if args.num_negotiation_rounds is not None else 0
        args.max_years = args.max_years if args.max_years is not None else 1901
        args.fixed_models = args.fixed_models if args.fixed_models is not None else "gemma3:4b,gpt-4o-mini"
    elif args.preset == "3p_neg":
        args.num_players = args.num_players if args.num_players is not None else 3
        args.num_negotiation_rounds = args.num_negotiation_rounds if args.num_negotiation_rounds is not None else 1
        args.max_years = args.max_years if args.max_years is not None else 1901
        args.fixed_models = args.fixed_models if args.fixed_models is not None else "gemma3:4b,gpt-4o-mini,gemma3:4b"
    elif args.preset == "wwi_2p":
        args.num_players = args.num_players if args.num_players is not None else 2
        # game_factory specifies how to create the game, implies specific powers
        args.game_factory = args.game_factory if args.game_factory is not None else "scenarios:wwi_two_player"
        # --players and --llm-models will be used by AgentManager directly if provided
        # Default fixed_models for this preset if not specified by --llm-models or --fixed_models
        if args.fixed_models is None and args.llm_models is None:
            args.fixed_models = "gemma3:4b,gemma3:4b" # Default for wwi_2p
        # Note: max_years, num_negotiation_rounds can be set by user or default for wwi_2p
        args.max_years = args.max_years if args.max_years is not None else 1918 # Example: WWI ends around 1918
        args.num_negotiation_rounds = args.num_negotiation_rounds if args.num_negotiation_rounds is not None else 0 # Often less negotiation in 2p

# -------------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Diplomacy game simulation with configurable parameters."
    )
    parser.add_argument(
        "--preset",
        choices=["2p_quick", "3p_neg", "wwi_2p"],
        help="Convenience aliases: 2p_quick, 3p_neg, or wwi_2p.",
    )
    parser.add_argument(
        "--game_factory",
        type=str,
        default=None,
        help="Path to a game factory function (e.g., 'module_name:function_name'). Overrides standard game creation."
    )
    parser.add_argument(
        "--players",
        type=str,
        default=None,
        help="Comma-separated list defining player types (e.g., 'llm,human,llm'). Used with game_factory."
    )
    parser.add_argument(
        "--llm-models", # Renamed from fixed_models for clarity when used with --players
        type=str,
        default=None,
        help="Comma-separated list of model IDs for LLM players, matching the order in --players. (e.g., 'gemma3:4b,gpt-4o-mini')."
    )
    # Arguments from original lm_game.py relevant to GameConfig
    parser.add_argument(
        "--power_name",
        type=str,
        default=None,
        help="Name of the primary power to control (e.g., FRANCE). Optional, less relevant with --players.",
    )
    parser.add_argument(
        "--model_id",
        type=str,
        default=None,
        help="Model ID for the primary power's LLM. Optional, less relevant with --llm-models.",
    )
    parser.add_argument(
        "--num_players",
        type=int,
        default=None, # Default is now handled by presets or game type
        help="Number of LLM-controlled players. Default: 7 for standard, 2 for wwi_2p.",
    )
    parser.add_argument(
        "--game_id_prefix",
        type=str,
        default="diplomacy_game",
        help="Prefix for the game ID if not explicitly set. Default: 'diplomacy_game'.",
    )
    parser.add_argument(
        "--game_id",
        type=str,
        default=None,
        help="Specific game ID to use. If None, one will be generated. Default: None.",
    )
    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level. Default: INFO.",
    )
    parser.add_argument(
        "--log_to_file",
        type=lambda x: (str(x).lower() == "true"),
        default=True,
        help="Enable/disable file logging. Default: True.",
    )
    parser.add_argument(
        "--log_dir",
        type=str,
        default=None,  # GameConfig handles default base if this is None
        help="Base directory for logs. Game-specific subfolder will be created here. Default: './logs'.",
    )
    parser.add_argument(
        "--perform_planning_phase",
        action="store_true",
        default=False,
        help="Enable the planning phase for each power. Default: False.",
    )
    parser.add_argument(
        "--num_negotiation_rounds",
        type=int,
        default=None, # Default handled by presets
        help="Number of negotiation rounds per movement phase. Default: 3 (standard), 0 (2p_quick/wwi_2p).",
    )
    parser.add_argument(
        "--negotiation_style",
        type=str,
        default="simultaneous",
        choices=["simultaneous", "round-robin"],
        help="Style of negotiation rounds. Default: 'simultaneous'.",
    )
    parser.add_argument(
        "--fixed_models", # Kept for backward compatibility / general use, but --llm-models is preferred with --players
        type=str,
        default=None,
        help="Comma-separated list of model IDs to assign to powers (e.g., 'gpt-4o,ollama/llama3'). Cycles if fewer than num_players. Use --llm-models with --players for specific assignments.",
    )
    parser.add_argument(
        "--randomize_fixed_models",
        action="store_true",
        default=False,
        help="Randomize assignment of fixed_models to powers. Default: False.",
    )
    parser.add_argument(
        "--exclude_powers",
        type=str,
        default=None,
        help="Comma-separated list of powers to exclude from LLM control (e.g., 'TURKEY,RUSSIA').",
    )
    parser.add_argument(
        "--max_years",
        type=int,
        default=None,  # Default handled by presets
        help="Maximum game year to simulate. Game ends after this year's Winter phase. Default: No limit (standard), 1901 (2p_quick), 1918 (wwi_2p).",
    )
    return parser.parse_args()


def get_game_from_factory(factory_path: str, player_names: List[str]) -> Game:
    """Dynamically imports and calls a game factory function."""
    module_name, func_name = factory_path.split(":")
    try:
        module = importlib.import_module(module_name)
        factory_func: Callable[..., Game] = getattr(module, func_name)
        # The wwi_two_player factory expects entente_player, central_player
        # We need to map player_names (which are the agent names) to these roles.
        # For wwi_2p, we expect two player_names.
        if func_name == "wwi_two_player" and len(player_names) == 2:
            # The factory uses these player_names (e.g., "ENTENTE_BLOC") in the game's metadata.
            # It no longer uses set_owner; AgentManager is responsible for mapping these
            # bloc names to the actual game powers (e.g., ENGLAND, FRANCE, RUSSIA for ENTENTE_BLOC).
            return factory_func(entente_player=player_names[0], central_player=player_names[1], italy_controller="NEUTRAL_ITALY")
        else:
            # Fallback for other factories or incorrect player count for wwi_2p
            # This part might need adjustment depending on other factory signatures
            logger.warning(f"Generic factory call for {factory_path}. Ensure player_names match factory needs.")
            return factory_func(*player_names) # Or however generic factories are called
    except (ImportError, AttributeError, TypeError) as e:
        logger.error(f"Error loading game factory '{factory_path}': {e}", exc_info=True)
        raise


async def main():
    args = parse_arguments()
    _apply_preset_to_args(args) # Apply presets first

    # Convert comma-separated strings from args to lists
    if args.llm_models:
        args.llm_models = [m.strip() for m in args.llm_models.split(",")]
    if args.fixed_models and isinstance(args.fixed_models, str): # Could be set by preset
        args.fixed_models = [m.strip() for m in args.fixed_models.split(",")]
    if args.players:
        args.players = [p.strip().lower() for p in args.players.split(",")]
    if args.exclude_powers:
        args.exclude_powers = [p.strip().upper() for p in args.exclude_powers.split(",")]

    # Default num_players if not set by preset or arg
    if args.num_players is None:
        if args.game_factory and "wwi_two_player" in args.game_factory:
            args.num_players = 2
        elif args.players:
            args.num_players = len(args.players)
        else:
            args.num_players = 7 # Default for standard game
    
    # Default num_negotiation_rounds if not set by preset or arg
    if args.num_negotiation_rounds is None:
        if args.preset in ["2p_quick", "wwi_2p"]:
            args.num_negotiation_rounds = 0
        else:
            args.num_negotiation_rounds = 3


    config = GameConfig(args)
    setup_logging(config)

    logger.info(f"Starting Diplomacy game: {config.game_id}")
    logger.info(f"Full configuration: {vars(config.args)}")
    start_time = time.time()

    game: Optional[Game] = None
    game_history: Optional[GameHistory] = None
    agent_manager: Optional[AgentManager] = None

    try:
        game_history = GameHistory()

        # AgentManager needs to handle the mapping of conceptual players (like "ENTENTE_BLOC")
        # to the actual game powers they control (e.g., ENGLAND, FRANCE, RUSSIA).
        # This is crucial for scenarios like wwi_two_player where the game factory
        # sets up a game with bloc names but the underlying diplomacy.Game object
        # still operates with standard powers. The AgentManager will need to ensure
        # that an agent representing a bloc acts for all its assigned standard powers.
        agent_manager = AgentManager(config) # AgentManager now uses config.args directly

        # Determine player names for the game and agents
        # These names will be the "powers" if a game factory like wwi_two_player is used.
        actual_player_names_for_game: List[str] = []
        if args.players:
            # Use names from --players argument if provided. These become the "powers" in the game context.
            # For wwi_2p, these would be like "ENTENTE_BLOC", "CENTRAL_BLOC"
            # We need unique names if multiple llms are just "llm"
            llm_count = 0
            for i, p_type in enumerate(args.players):
                if p_type == "llm":
                    actual_player_names_for_game.append(f"LLM_PLAYER_{i+1}")
                    llm_count +=1
                else:
                    actual_player_names_for_game.append(f"{p_type.upper()}_{i+1}") # e.g. HUMAN_1
            
            # If llm_models are not specified, but fixed_models are, and match llm_count, use fixed_models.
            # Or, if llm_models are not specified, and fixed_models has enough models for llm_count, use them.
            # The primary source for models with --players should be --llm-models.
            if not args.llm_models and args.fixed_models and len(args.fixed_models) >= llm_count:
                args.llm_models = args.fixed_models[:llm_count]
                logger.info(f"Using fixed_models for llm_models with --players: {args.llm_models}")
            elif not args.llm_models and llm_count > 0:
                logger.error("LLM players specified via --players, but --llm-models not provided or insufficient from --fixed_models.")
                sys.exit(1)


        # 3. Create Game Instance
        if args.game_factory:
            if not actual_player_names_for_game:
                # Default player names if --players not specified but factory is.
                # For wwi_2p, this means we need two default names.
                if "wwi_two_player" in args.game_factory:
                     actual_player_names_for_game = ["ENTENTE_BLOC", "CENTRAL_BLOC"]
                else: # Generic factory, this might not be enough
                    logger.error("Game factory specified, but --players not provided to define player names for the factory.")
                    sys.exit(1)
            game = get_game_from_factory(args.game_factory, actual_player_names_for_game)
            logger.info(f"Game created using factory: {args.game_factory}")
            logger.info(f"Game powers after factory: {list(game.powers.keys())}")
        else:
            game = Game() # Standard game
            logger.info("Standard game created.")
            # For standard game, actual_player_names_for_game are the standard powers unless excluded
            standard_powers = list(game.powers.keys())
            if args.exclude_powers:
                actual_player_names_for_game = [p for p in standard_powers if p not in args.exclude_powers]
            else:
                actual_player_names_for_game = standard_powers
            
            if args.num_players is not None and args.num_players < len(actual_player_names_for_game):
                 actual_player_names_for_game = actual_player_names_for_game[:args.num_players]


        # 5. Assign models and Initialize Agents
        # The "powers" for AgentManager are now actual_player_names_for_game
        # These could be "FRANCE", "GERMANY" for standard, or "ENTENTE_BLOC", "CENTRAL_BLOC" for wwi_2p
        
        powers_and_models_map: Dict[str, str] = {}
        if args.players and args.llm_models:
            llm_model_idx = 0
            for i, p_type in enumerate(args.players):
                player_name_for_game = actual_player_names_for_game[i] # e.g. LLM_PLAYER_1
                if p_type == "llm":
                    if llm_model_idx < len(args.llm_models):
                        powers_and_models_map[player_name_for_game] = args.llm_models[llm_model_idx]
                        llm_model_idx += 1
                    else:
                        logger.error(f"Not enough models in --llm-models for all 'llm' players in --players.")
                        sys.exit(1)
                # elif p_type == "human": # Placeholder for human/other agent types
                #    logger.info(f"Player {player_name_for_game} is human, no LLM model assigned.")
        elif not args.game_factory: # Standard game assignment if not using --players
            # This uses the original logic of assigning models from fixed_models or model_id
            # to a subset of standard game powers.
            # Ensure actual_player_names_for_game contains the powers to be LLM controlled.
            llm_controlled_powers = agent_manager.get_llm_controlled_powers(
                all_game_powers=actual_player_names_for_game, # These are the powers active in the game
                num_llm_players=config.args.num_players or len(actual_player_names_for_game), # num_players from config
                primary_power_name=config.args.power_name,
                primary_model_id=config.args.model_id,
                fixed_models_list=config.args.fixed_models if isinstance(config.args.fixed_models, list) else None,
                randomize_assignment=config.args.randomize_fixed_models
            )
            powers_and_models_map = llm_controlled_powers # The function now returns the map directly
        else: # Game factory used, but --players not, this is ambiguous.
              # For wwi_2p, actual_player_names_for_game = ["ENTENTE_BLOC", "CENTRAL_BLOC"]
              # We need to assign models to these.
            if "wwi_two_player" in args.game_factory and len(actual_player_names_for_game) == 2:
                models_to_assign = []
                if args.llm_models and len(args.llm_models) >= 2:
                    models_to_assign = args.llm_models[:2]
                elif args.fixed_models and len(args.fixed_models) >= 2: # fixed_models can be string or list here
                    models_list = args.fixed_models if isinstance(args.fixed_models, list) else [m.strip() for m in args.fixed_models.split(",")]
                    models_to_assign = models_list[:2]
                else: # Fallback to preset default if any, or error
                    # The preset for wwi_2p already defaults fixed_models if llm_models isn't given.
                     models_list_preset = [m.strip() for m in "gemma3:4b,gemma3:4b".split(",")] # default
                     if args.fixed_models and isinstance(args.fixed_models, str): # from preset potentially
                         models_list_preset = [m.strip() for m in args.fixed_models.split(",")]
                     elif args.fixed_models and isinstance(args.fixed_models, list):
                         models_list_preset = args.fixed_models

                     if len(models_list_preset) >= 2:
                         models_to_assign = models_list_preset[:2]
                     else:
                        logger.error("For wwi_2p preset, not enough models specified via --llm-models or --fixed_models.")
                        sys.exit(1)
                
                powers_and_models_map[actual_player_names_for_game[0]] = models_to_assign[0]
                powers_and_models_map[actual_player_names_for_game[1]] = models_to_assign[1]

        if not powers_and_models_map:
            logger.error("No LLM-controlled powers were assigned. Check --players, --llm-models, or game setup. Exiting.")
            sys.exit(1)

        logger.info(f"LLM Agents to be initialized for: {powers_and_models_map}")
        agent_manager.initialize_agents(powers_and_models_map, game) # Pass game to initialize_agents

        if not agent_manager.agents:
            logger.error("Failed to initialize any agents. Exiting.")
            sys.exit(1)

        orchestrator = PhaseOrchestrator(
            game_config=config,
            agent_manager=agent_manager,
            get_valid_orders_func=get_valid_orders,
        )

        await orchestrator.run_game_loop(game, game_history)

    except KeyboardInterrupt:
        logger.info("Game interrupted by user (KeyboardInterrupt). Saving partial results...")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the game: {e}", exc_info=True)
        detailed_error = traceback.format_exc()
        logger.error(f"Detailed traceback:\n{detailed_error}")
    finally:
        if game and game_history and agent_manager:
            logger.info("Game loop finished or interrupted. Processing final results...")
            results_processor = GameResultsProcessor(config) # config now holds args
            results_processor.log_final_results(game)
            if config.args.log_to_file: # Access log_to_file via config.args
                results_processor.save_game_state(game, game_history)
                if agent_manager.agents:
                    results_processor.save_agent_manifestos(agent_manager.agents) # Pass dict of agents
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
        initial_logger = logging.getLogger(__name__)
        initial_logger.error(f"Critical error in asyncio.run(main()): {e}", exc_info=True)
        detailed_traceback = traceback.format_exc()
        initial_logger.error(f"Detailed traceback:\n{detailed_traceback}")
        sys.exit(1)
