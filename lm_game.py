import argparse
import asyncio
import logging
import os
import sys
import importlib

_project_root_dir = os.path.dirname(os.path.abspath(__file__))
if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

import time
import traceback
from typing import (
    Optional,
    Callable,
    Any,
    List,
    Dict,
)

import dotenv
from diplomacy import Game

from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager

from ai_diplomacy.orchestrators.phase_orchestrator import PhaseOrchestrator

from ai_diplomacy.game_results import GameResultsProcessor
from ai_diplomacy.game_history import GameHistory

from ai_diplomacy.general_utils import (
    get_valid_orders,
)

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Diplomacy game simulation with configurable parameters. Primarily uses a TOML config file."
    )
    parser.add_argument(
        "--game_config_file",
        "--config",
        type=str,
        default=None, # Default is None, so GameConfig will raise error if not provided (unless in mock mode)
        help="Path to a TOML file containing game configuration. This is the primary way to configure the game.",
    )
    # All other arguments are removed as they are now sourced from the TOML file via GameConfig.
    return parser.parse_args()


def get_game_from_factory(
    game_factory_callable: Callable[..., Game],
    factory_path_name: str, # For logging/identification
    player_names: List[str]
) -> Game:
    """
    Calls the provided game factory callable with specific argument handling for known factories.
    """
    # factory_path_name is used to identify the factory, e.g. "scenarios.wwi_two_player"
    if "wwi_two_player" in factory_path_name: # Check if it's the WWI scenario
        if len(player_names) == 3:
            logger.info(
                f"Calling wwi_two_player factory ('{factory_path_name}') with Entente: {player_names[0]}, "
                f"Central: {player_names[1]}, Italy: {player_names[2]}"
            )
            return game_factory_callable(
                entente_player=player_names[0],
                central_player=player_names[1],
                italy_controller=player_names[2],
            )
        else:
            logger.error(
                f"wwi_two_player factory ('{factory_path_name}') expects 3 player names (Entente, Central, Italy) "
                f"but received {len(player_names)}: {player_names}. "
                "Please check agent definitions in the TOML configuration."
            )
            raise ValueError(
                f"Incorrect number of players for wwi_two_player factory: expected 3, got {len(player_names)}"
            )
    else:
        # This path should ideally not be hit if we only support wwi_two_player,
        # as GameConfig would have already failed if an unknown factory was specified.
        logger.warning(
            f"Calling a generic or unknown game factory ('{factory_path_name}'). "
            "Attempting to pass player_names as positional arguments. "
            "This might fail if the factory expects specific named arguments."
        )
        try:
            return game_factory_callable(*player_names)
        except TypeError as e:
            logger.error(
                f"Error calling factory '{factory_path_name}' with player_names {player_names}: {e}. "
                "The factory might require specific named arguments or a different number of arguments."
            )
            raise
    # Removed dynamic importlib loading as game_factory_callable is now passed directly.


async def main():
    args = parse_arguments()
    # Removed all CLI argument processing blocks. GameConfig now handles this.

    config = GameConfig(args) # GameConfig now loads everything from TOML based on args.game_config_file
    # GameConfig constructor now calls setup_logging directly.

    logger.info(f"Starting Diplomacy game: {config.game_id}") # config.game_id is now set within GameConfig
    if config.players_list:
        logger.info(f"Players List (from config): {config.players_list}")
        logger.info(f"Agent Types List (from config): {config.agent_types_list}")
        logger.info(f"Bloc Definitions List (from config): {config.bloc_definitions_list}")
        logger.info(f"LLM Models List (from config): {config.llm_models_list}")

    start_time = time.time()

    game: Optional[Game] = None
    # game_history is part of config (config.game_history)
    agent_manager: Optional[AgentManager] = None

    try:
        # game_history = GameHistory() # This is redundant, config.game_history is used.
        agent_manager = AgentManager(config)

        agent_configurations: Dict[str, Dict[str, Any]] = {}
            # actual_player_names_for_game will be config.players_list, which is populated by GameConfig from TOML.
            actual_player_names_for_game: List[str] = config.players_list

            if not config.players_list or not config.agent_types_list:
                logger.error("Missing 'players_list' or 'agent_types_list' in GameConfig. These should be populated from TOML 'agents' list.")
                sys.exit(1)

            # Validate lengths of lists from config
            num_players = len(config.players_list)
            if not (num_players == len(config.agent_types_list) == len(config.llm_models_list) == len(config.agent_countries_list)):
                logger.error(
                    "Mismatch in lengths of agent configuration lists from GameConfig (TOML): "
                    f"Players: {num_players}, Types: {len(config.agent_types_list)}, "
                    f"Models: {len(config.llm_models_list)}, Countries: {len(config.agent_countries_list)}. "
                    "Ensure each agent entry in TOML is complete."
                )
                sys.exit(1)

            # Parse bloc definitions from config.bloc_definitions_list (which is like ["bloc_name1:POWER1;POWER2", ...])
            parsed_bloc_defs: Dict[str, List[str]] = {}
            if config.bloc_definitions_list:
                for bloc_def_str in config.bloc_definitions_list:
                    parts = bloc_def_str.split(":", 1)
                    if len(parts) == 2:
                        bloc_name_def, powers_str = parts
                        parsed_bloc_defs[bloc_name_def.strip()] = [
                            p.strip().upper() for p in powers_str.split(";")
                        ]
                    else:
                        logger.warning(f"Invalid bloc definition format in TOML: '{bloc_def_str}'. Skipping.")

            for i, player_identifier in enumerate(config.players_list):
                agent_type = config.agent_types_list[i].lower() # Ensure lowercase comparison
                model_for_this_agent = config.llm_models_list[i]
                country_for_this_agent = config.agent_countries_list[i] # This is Optional[str]

                current_agent_setup: Dict[str, Any] = {"type": agent_type}
                current_agent_setup["model_id"] = model_for_this_agent # Will be "" if not LLM type, that's fine.

                if agent_type in ["llm", "neutral", "null"]:
                    if country_for_this_agent:
                        current_agent_setup["country"] = country_for_this_agent
                    else:
                        # For these types, 'country' is important. If GameConfig didn't ensure one, log error.
                        # GameConfig's _parse_agent_data_from_toml should fill 'country' for these.
                        logger.error(
                            f"Agent type '{agent_type}' for player '{player_identifier}' "
                            f"is missing 'country' in its TOML definition. This is required."
                    )
                        # Potentially sys.exit(1) or let AgentManager handle it if it can.
                        # For now, we'll let it proceed and AgentManager might raise an error.
                        current_agent_setup["country"] = player_identifier # Fallback, might not be valid for game
                elif agent_type == "bloc_llm":
                    current_agent_setup["bloc_name"] = player_identifier # The player_identifier is the bloc name
                    if player_identifier in parsed_bloc_defs:
                        current_agent_setup["controlled_powers"] = parsed_bloc_defs[player_identifier]
                else:
                        logger.error(
                            f"No definition found for bloc: {player_identifier} in 'bloc_definitions_list' from TOML. "
                            "Ensure it is defined in the 'agents' list with type 'bloc_llm' and a 'powers' list."
                    )
                        continue # Skip this agent configuration
                # "human" type is not expected for wwi_test.toml, so not explicitly handled here.
                # If other types are added, they would need handling.
                else:
                    logger.warning(
                        f"Unknown or unsupported agent type: '{agent_type}' for player '{player_identifier}' from TOML. Skipping."
                    )
                    continue
                agent_configurations[player_identifier] = current_agent_setup

        if not agent_configurations:
            logger.error(
                    "No valid agent configurations were created. "
                    "Please ensure the 'agents' list in the TOML config file is correctly defined."
            )
            sys.exit(1)

            # Use the game_factory callable and its path_name directly from config
            if config.game_factory and config.game_factory_path:
                if not actual_player_names_for_game and "wwi_two_player" not in config.game_factory_path:
                     logger.error(
                        f"Game factory '{config.game_factory_path}' specified, but no player/agent identifiers found in configuration."
                )
                     sys.exit(1)

                game = get_game_from_factory(
                    config.game_factory, # The callable factory
                    config.game_factory_path, # The path string for identification
                    actual_player_names_for_game
            )
            logger.info(
                    f"Game created using factory: {config.game_factory_path}. Agent Identifiers involved: {actual_player_names_for_game}"
            )
            else:
                # This case should ideally be prevented by GameConfig raising an error if factory is missing (unless mock mode)
                logger.error("Game factory (callable or path) not found in GameConfig. Cannot create game.")
                sys.exit(1)

            config.game_instance = game # Assign the created game instance to config

        logger.info(f"Final agent configurations to be initialized: {agent_configurations}")
        agent_manager.initialize_agents(agent_configurations)

        if not agent_manager.agents:
            logger.error("Failed to initialize any agents. Exiting.")
            sys.exit(1)

        try:
            config.build_and_validate_agent_maps(
                game_instance=game,
                agent_configurations=agent_configurations,
                initialized_agents=agent_manager.agents,
            )
        except ValueError as e:
            logger.error(f"Game setup validation failed: {e}")
            sys.exit(1)

        powers_and_models_map: Dict[str, str] = {}
        for agent_id, agent_config_details in agent_configurations.items():
            model_id = agent_config_details.get("model_id")
            if agent_id in config.agent_to_powers_map and model_id:
                for power_name in config.agent_to_powers_map[agent_id]:
                    powers_and_models_map[power_name] = model_id
        config.powers_and_models = powers_and_models_map
        logger.info(f"Reconstructed config.powers_and_models for orchestrator: {config.powers_and_models}")

        orchestrator = PhaseOrchestrator(
            game_config=config,
            agent_manager=agent_manager,
            get_valid_orders_func=get_valid_orders,
        )

        await orchestrator.run_game_loop(game, config.game_history) # Use config.game_history

    except KeyboardInterrupt:
        logger.info("Game interrupted by user (KeyboardInterrupt). Saving partial results...")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the game: {e}", exc_info=True)
        detailed_error = traceback.format_exc()
        logger.error(f"Detailed traceback:\n{detailed_error}")
    finally:
        # Use config.game_history instead of local game_history
        if game and config.game_history and agent_manager:
            logger.info("Game loop finished or interrupted. Processing final results...")
            results_processor = GameResultsProcessor(config)
            results_processor.log_final_results(game)
            if config.log_to_file:
                results_processor.save_game_state(game, config.game_history) # Use config.game_history
                if agent_manager.agents:
                    results_processor.save_agent_manifestos(agent_manager.agents)
                else:
                    logger.warning("AgentManager agents not initialized, skipping manifesto saving.")
            logger.info(
                f"Results processing complete. Total game time: {time.time() - start_time:.2f} seconds."
            )
            logger.info(f"Output files are located in: {config.game_id_specific_log_dir}")
        else:
            logger.error(
                "Game object, game history, or agent manager was not initialized. No results to save."
            )
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
