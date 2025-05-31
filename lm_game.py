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
        # For 2p_quick, if players/types not set, default to two LLMs
        args.players = args.players if args.players is not None else "AUSTRIA,ENGLAND" # Example powers
        args.agent_types = args.agent_types if args.agent_types is not None else "llm,llm"
        args.llm_models = args.llm_models if args.llm_models is not None else "gemma3:4b,gpt-4o-mini"
        args.fixed_models = None # llm_models takes precedence for specific assignments
    elif args.preset == "3p_neg":
        args.num_players = args.num_players if args.num_players is not None else 3
        args.num_negotiation_rounds = args.num_negotiation_rounds if args.num_negotiation_rounds is not None else 1
        args.max_years = args.max_years if args.max_years is not None else 1901
        args.players = args.players if args.players is not None else "AUSTRIA,ENGLAND,FRANCE" # Example powers
        args.agent_types = args.agent_types if args.agent_types is not None else "llm,llm,llm"
        args.llm_models = args.llm_models if args.llm_models is not None else "gemma3:4b,gpt-4o-mini,gemma3:4b"
        args.fixed_models = None # llm_models takes precedence
    elif args.preset == "5p_standard":
        args.players = args.players if args.players is not None else "ENGLAND,FRANCE,GERMANY,RUSSIA,TURKEY,ITALY,AUSTRIA"
        args.agent_types = args.agent_types if args.agent_types is not None else "llm,llm,llm,llm,llm,neutral,neutral"
        args.llm_models = args.llm_models if args.llm_models is not None else "gemma3:4b,gpt-4o-mini,gemma3:4b,gpt-4o-mini,gemma3:4b"
        args.game_factory = args.game_factory if args.game_factory is not None else None # Standard game
        args.num_negotiation_rounds = args.num_negotiation_rounds if args.num_negotiation_rounds is not None else 3
        args.max_years = args.max_years if args.max_years is not None else 1905
    elif args.preset == "6p_standard":
        args.players = args.players if args.players is not None else "ENGLAND,FRANCE,GERMANY,RUSSIA,TURKEY,AUSTRIA,ITALY"
        args.agent_types = args.agent_types if args.agent_types is not None else "llm,llm,llm,llm,llm,llm,neutral"
        args.llm_models = args.llm_models if args.llm_models is not None else "gemma3:4b,gpt-4o-mini,gemma3:4b,gpt-4o-mini,gemma3:4b,gpt-4o-mini"
        args.game_factory = args.game_factory if args.game_factory is not None else None # Standard game
        args.num_negotiation_rounds = args.num_negotiation_rounds if args.num_negotiation_rounds is not None else 3
        args.max_years = args.max_years if args.max_years is not None else 1905
    elif args.preset == "wwi_2p":
        args.num_players = args.num_players if args.num_players is not None else 2 # Number of blocs + neutral
        args.game_factory = args.game_factory if args.game_factory is not None else "scenarios:wwi_two_player"
        args.players = args.players if args.players is not None else "ENTENTE_BLOC,CENTRAL_BLOC,NEUTRAL_ITALY"
        args.agent_types = args.agent_types if args.agent_types is not None else "bloc_llm,bloc_llm,neutral"
        args.bloc_definitions = args.bloc_definitions if args.bloc_definitions is not None else "ENTENTE_BLOC:ENG;FRA;RUS,CENTRAL_BLOC:GER;AUS;TUR"
        args.llm_models = args.llm_models if args.llm_models is not None else "gemma3:4b,gemma3:4b" # For the two blocs
        args.fixed_models = None # llm_models takes precedence
        args.max_years = args.max_years if args.max_years is not None else 1918
        args.num_negotiation_rounds = args.num_negotiation_rounds if args.num_negotiation_rounds is not None else 0

# -------------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Diplomacy game simulation with configurable parameters."
    )
    parser.add_argument(
        "--preset",
        choices=["2p_quick", "3p_neg", "5p_standard", "6p_standard", "wwi_2p"],
        help="Convenience aliases: 2p_quick, 3p_neg, 5p_standard, 6p_standard, or wwi_2p.",
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
        help="Comma-separated list of agent identifiers (e.g., 'FRANCE', 'ENTENTE_BLOC')."
    )
    parser.add_argument(
        "--agent-types",
        type=str,
        default=None,
        help="Comma-separated list of agent types (e.g., 'llm,neutral,bloc_llm'), corresponding to --players."
    )
    parser.add_argument(
        "--bloc-definitions",
        type=str,
        default=None,
        help="Comma-separated list of bloc definitions (e.g., 'ENTENTE_BLOC:ENG;FRA;RUS,OTHER_BLOC:GER;AUS')."
    )
    parser.add_argument(
        "--llm-models",
        type=str,
        default=None,
        help="Comma-separated list of model IDs for 'llm' or 'bloc_llm' type agents, in order of appearance in --players. (e.g., 'gemma3:4b,gpt-4o-mini')."
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

    # Convert comma-separated strings from args to lists and store them on args
    # This makes them available to GameConfig
    if args.llm_models:
        args.llm_models_list = [m.strip() for m in args.llm_models.split(",")]
    else:
        args.llm_models_list = [] # Ensure it's a list

    if args.fixed_models and isinstance(args.fixed_models, str):
        args.fixed_models_list = [m.strip() for m in args.fixed_models.split(",")]
    elif args.fixed_models: # Already a list from preset
        args.fixed_models_list = args.fixed_models
    else:
        args.fixed_models_list = []


    if args.players:
        # Keep case for player identifiers like "ENTENTE_BLOC"
        args.players_list = [p.strip() for p in args.players.split(",")]
    else:
        args.players_list = [] # Ensure it's a list

    if args.agent_types:
        args.agent_types_list = [t.strip().lower() for t in args.agent_types.split(",")]
    else:
        args.agent_types_list = []

    if args.bloc_definitions:
        args.bloc_definitions_list = [d.strip() for d in args.bloc_definitions.split(",")]
    else:
        args.bloc_definitions_list = []

    if args.exclude_powers:
        args.exclude_powers_list = [p.strip().upper() for p in args.exclude_powers.split(",")]
    else:
        args.exclude_powers_list = []

    # Pass the modified args to GameConfig
    config = GameConfig(args) # GameConfig will pick up *_list attributes
    setup_logging(config)

    logger.info(f"Starting Diplomacy game: {config.game_id}")
    # Log the lists from the config object where they are stored
    logger.info(f"Players List: {config.players_list}")
    logger.info(f"Agent Types List: {config.agent_types_list}")
    logger.info(f"Bloc Definitions List: {config.bloc_definitions_list}")
    logger.info(f"LLM Models List: {config.args.llm_models_list}") # from args
    logger.info(f"Fixed Models List: {config.args.fixed_models_list}") # from args
    start_time = time.time()

    game: Optional[Game] = None
    game_history: Optional[GameHistory] = None
    agent_manager: Optional[AgentManager] = None

    try:
        game_history = GameHistory()
        agent_manager = AgentManager(config)

        # Construct agent_configurations
        agent_configurations: Dict[str, Dict[str, Any]] = {}
        actual_player_names_for_game: List[str] = [] # For game factory

        if config.players_list and config.agent_types_list:
            if len(config.players_list) != len(config.agent_types_list):
                logger.error("--players and --agent-types must have the same number of elements.")
                sys.exit(1)

            actual_player_names_for_game = config.players_list # These are the entities for the game

            llm_model_idx = 0
            # Use llm_models_list from args, or fixed_models_list as fallback
            llm_models_available = config.args.llm_models_list or config.args.fixed_models_list or []

            parsed_bloc_defs: Dict[str, List[str]] = {}
            if config.bloc_definitions_list:
                for bloc_def_str in config.bloc_definitions_list:
                    parts = bloc_def_str.split(":", 1)
                    if len(parts) == 2:
                        bloc_name_def, powers_str = parts
                        parsed_bloc_defs[bloc_name_def.strip()] = [p.strip().upper() for p in powers_str.split(";")]
                    else:
                        logger.warning(f"Invalid bloc definition format: {bloc_def_str}. Skipping.")

            for i, player_identifier in enumerate(config.players_list):
                agent_type = config.agent_types_list[i]
                current_agent_setup: Dict[str, Any] = {"type": agent_type}

                if agent_type == "llm":
                    current_agent_setup["country"] = player_identifier
                    if llm_model_idx < len(llm_models_available):
                        current_agent_setup["model_id"] = llm_models_available[llm_model_idx]
                        llm_model_idx += 1
                    else:
                        logger.warning(f"Not enough models for LLM agent: {player_identifier}. Using default or None.")
                        current_agent_setup["model_id"] = None
                elif agent_type == "neutral":
                    current_agent_setup["country"] = player_identifier
                    # model_id is not strictly needed, NeutralAgent sets its own
                elif agent_type == "bloc_llm":
                    current_agent_setup["bloc_name"] = player_identifier
                    if player_identifier in parsed_bloc_defs:
                        current_agent_setup["controlled_powers"] = parsed_bloc_defs[player_identifier]
                    else:
                        logger.error(f"No definition found for bloc: {player_identifier} in --bloc-definitions. Skipping.")
                        continue
                    if llm_model_idx < len(llm_models_available):
                        current_agent_setup["model_id"] = llm_models_available[llm_model_idx]
                        llm_model_idx += 1
                    else:
                        logger.warning(f"Not enough models for BlocLLM agent: {player_identifier}. Using default or None.")
                        current_agent_setup["model_id"] = None
                elif agent_type == "human":
                    current_agent_setup["country"] = player_identifier
                    logger.info(f"Human player defined: {player_identifier}. Manual control assumed. Skipping agent creation via AgentManager.")
                    continue # AgentManager doesn't create human agents
                else:
                    logger.warning(f"Unknown agent type: {agent_type} for player {player_identifier}. Skipping.")
                    continue
                
                agent_configurations[player_identifier] = current_agent_setup

        elif not config.args.game_factory : # No players list, standard game. Default to 7 LLM players if nothing else.
            logger.info("No --players list provided. Assuming standard 7-power game with LLMs or specified num_players.")
            game_temp = Game() # Temp game to get standard powers
            standard_powers = list(game_temp.powers.keys())

            num_llms_to_create = config.num_players if config.num_players is not None else 7
            actual_player_names_for_game = standard_powers # All standard powers are potential players

            llm_models_available = config.args.llm_models_list or config.args.fixed_models_list or []
            llm_model_idx = 0

            for i, power_name in enumerate(standard_powers):
                if config.exclude_powers_list and power_name in config.exclude_powers_list:
                    agent_configurations[power_name] = {"type": "neutral", "country": power_name}
                elif i < num_llms_to_create:
                    model_to_use = None
                    if llm_model_idx < len(llm_models_available):
                        model_to_use = llm_models_available[llm_model_idx]
                        llm_model_idx +=1
                    elif len(llm_models_available) > 0 : # Cycle if models provided but fewer than players
                        model_to_use = llm_models_available[llm_model_idx % len(llm_models_available)]
                        llm_model_idx +=1
                    else:
                         logger.warning(f"Not enough models for standard LLM player {power_name}. Model set to None.")
                    agent_configurations[power_name] = {"type": "llm", "country": power_name, "model_id": model_to_use}
                else: # Remaining players are neutral
                    agent_configurations[power_name] = {"type": "neutral", "country": power_name}
            actual_player_names_for_game = [p for p in standard_powers if not (config.exclude_powers_list and p in config.exclude_powers_list)]


        if not agent_configurations:
            logger.error("No agent configurations created. Check arguments. Exiting.")
            sys.exit(1)

        # Create Game Instance
        if config.args.game_factory:
            if not actual_player_names_for_game:
                 # This case should ideally be handled by presets or arg validation for factories
                logger.error("Game factory specified, but no player names determined (e.g. from --players).")
                sys.exit(1)
            game = get_game_from_factory(config.args.game_factory, actual_player_names_for_game)
            logger.info(f"Game created using factory: {config.args.game_factory}. Players: {actual_player_names_for_game}")
        else:
            game = Game() # Standard game
            logger.info("Standard game created.")
            # Filter game.powers if some are excluded and became neutral.
            # For standard game, actual_player_names_for_game was already set to non-excluded standard powers.

        logger.info(f"Agents to be initialized: {agent_configurations}")
        agent_manager.initialize_agents(agent_configurations)

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
            if config.log_to_file: # Access log_to_file via config itself
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
