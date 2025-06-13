import logging
import os
import sys
import time
import traceback
from typing import Any, Callable, Dict, List, Optional
import asyncio
import importlib
from types import SimpleNamespace

import dotenv
from diplomacy import Game

from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.game_results import GameResultsProcessor
from ai_diplomacy.general_utils import (
    get_valid_orders,
)
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.orchestrators.phase_orchestrator import PhaseOrchestrator

# Add project root to path
_project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

dotenv.load_dotenv()

# Logger setup
setup_logging(log_level="INFO")  # Default log level
logger = logging.getLogger("DiplomacyGame")


def get_game_from_factory(factory_path: str, player_names: List[str]) -> Game:
    """Dynamically imports and calls a game factory function."""
    if ":" in factory_path:
        module_name, func_name = factory_path.split(":")
    elif "." in factory_path:
        module_name, func_name = factory_path.rsplit(".", 1)
    else:
        raise ValueError(
            f"factory_path '{factory_path}' must contain ':' or '.' to separate module and function."
        )

    try:
        module = importlib.import_module(module_name)
        factory_func: Callable[..., Game] = getattr(module, func_name)
        if func_name == "wwi_two_player":
            if len(player_names) == 3:
                logger.info(
                    f"Calling wwi_two_player factory with Entente: {player_names[0]}, "
                    f"Central: {player_names[1]}, Italy: {player_names[2]}"
                )
                return factory_func(
                    entente_player=player_names[0],
                    central_player=player_names[1],
                    italy_controller=player_names[2],
                )
            else:
                logger.error(
                    f"wwi_two_player factory expects 3 player names (Entente, Central, Italy) "
                    f"but received {len(player_names)}: {player_names}. "
                    "Please check agent definitions in the TOML configuration."
                )
                raise ValueError(
                    f"Incorrect number of players for wwi_two_player factory: expected 3, got {len(player_names)}"
                )
        else:
            logger.warning(
                f"Generic factory call for {factory_path}. Ensuring player_names match factory needs."
            )
            try:
                return factory_func(*player_names)
            except TypeError as e:
                logger.error(
                    f"Error calling generic factory {factory_path} with player_names {player_names}: {e}"
                )
                logger.error(
                    "This may indicate that the factory requires specific named arguments "
                    "or a different number of arguments than provided."
                )
                raise
    except (ImportError, AttributeError, TypeError) as e:
        logger.error(f"Error loading game factory '{factory_path}': {e}", exc_info=True)
        raise


def prepare_agent_configurations(
    config: GameConfig,
) -> tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    Parses agent configurations from the GameConfig object.
    This logic was moved from main() to simplify the game setup flow.
    """
    if not (config.players_list and config.agent_types_list):
        logger.error("Agent 'players' and 'agent_types' lists are required in config but not found.")
        sys.exit(1)

    llm_agent_count = sum(1 for at in config.agent_types_list if at in ["llm", "bloc_llm"])
    if llm_agent_count > len(config.llm_models_list):
        logger.error(
            f"Insufficient LLM models provided. Found {llm_agent_count} LLM-based agents, "
            f"but only {len(config.llm_models_list)} models are defined."
        )
        sys.exit(1)

    agent_configurations: Dict[str, Dict[str, Any]] = {}
    actual_player_names_for_game = config.players_list
    llm_models_to_use = config.llm_models_list or config.fixed_models or []
    llm_model_idx = 0

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
        model_for_this_agent = None
        if agent_type in ["llm", "bloc_llm"]:
            if llm_model_idx < len(llm_models_to_use):
                model_for_this_agent = llm_models_to_use[llm_model_idx]
                llm_model_idx += 1
            else:
                logger.warning(
                    f"Not enough models for {agent_type} agent: {player_identifier}. Using default or None."
                )
        current_agent_setup["model_id"] = model_for_this_agent

        if agent_type in ["llm", "neutral", "null"]:
            country_for_agent = config.agent_countries_list[i]
            if country_for_agent:
                current_agent_setup["country"] = country_for_agent
            else:
                logger.warning(
                    f"Agent type '{agent_type}' for player '{player_identifier}' "
                    f"expects a 'country' in TOML, but it's missing or empty. "
                    f"Using player identifier as fallback."
                )
                current_agent_setup["country"] = player_identifier
        elif agent_type == "bloc_llm":
            current_agent_setup["bloc_name"] = player_identifier
            if player_identifier in parsed_bloc_defs:
                current_agent_setup["controlled_powers"] = parsed_bloc_defs[player_identifier]
            else:
                logger.error(
                    f"No definition found for bloc: {player_identifier}. "
                    "Ensure it is defined in TOML's 'bloc_definitions'. Skipping."
                )
                continue
        elif agent_type == "human":
            current_agent_setup["country"] = player_identifier
            logger.info(
                f"Human player defined: {player_identifier}. Manual control assumed. Skipping agent creation."
            )
            continue
        else:
            logger.warning(f"Unknown agent type: {agent_type} for player {player_identifier}. Skipping.")
            continue
        agent_configurations[player_identifier] = current_agent_setup

    return agent_configurations, actual_player_names_for_game


def process_game_results(
    config: GameConfig,
    game: Game,
    game_history: GameHistory,
    agent_manager: AgentManager,
    start_time: float,
):
    """Logs and saves final game results and artifacts."""
    logger.info("Game loop finished or interrupted. Processing final results...")
    results_processor = GameResultsProcessor(config)
    results_processor.log_final_results(game)
    if config.log_to_file:
        results_processor.save_game_state(game, game_history)
        if agent_manager.agents:
            results_processor.save_agent_manifestos(agent_manager.agents)
        else:
            logger.warning("AgentManager agents not initialized, skipping manifesto saving.")
    logger.info(f"Results processing complete. Total game time: {time.time() - start_time:.2f} seconds.")
    logger.info(f"Output files are located in: {config.game_id_specific_log_dir}")


async def main():
    # Replaced argparse with direct sys.argv handling for config file
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        # As per user context, defaulting to wwi_test.toml
        config_file = "wwi_test.toml"
        logger.info(f"No config file provided. Defaulting to '{config_file}'")
        logger.info(f"Usage: python {sys.argv[0]} <path_to_config.toml>")

    if not os.path.exists(config_file):
        logger.error(f"ERROR: Configuration file not found at '{config_file}'")
        sys.exit(1)

    # We now only pass the config file path to GameConfig.
    # GameConfig is now responsible for all parameter loading.
    # Using a simple namespace object to maintain compatibility with GameConfig constructor
    args = SimpleNamespace(game_config_file=config_file)

    config = GameConfig(args)
    setup_logging(config)

    logger.info(f"Starting Diplomacy game: {config.game_id}")
    if config.players_list:
        logger.info(f"Players List (from config): {config.players_list}")
        logger.info(f"Agent Types List (from config): {config.agent_types_list}")
        logger.info(f"Bloc Definitions List (from config): {config.bloc_definitions_list}")
        logger.info(f"LLM Models List (from config): {config.llm_models_list}")

    start_time = time.time()

    game: Optional[Game] = None
    game_history: Optional[GameHistory] = None
    agent_manager: Optional[AgentManager] = None

    try:
        game_history = GameHistory()
        agent_manager = AgentManager(config)

        (
            agent_configurations,
            actual_player_names_for_game,
        ) = prepare_agent_configurations(config)

        if not agent_configurations:
            logger.error(
                "No valid agent configurations were created. "
                "Please check agent definitions in your TOML config file."
            )
            sys.exit(1)

        game_factory_to_use = config.game_factory_path

        if game_factory_to_use:
            if not actual_player_names_for_game and "wwi_two_player" not in game_factory_to_use:
                logger.error(
                    f"Game factory '{game_factory_to_use}' specified, but no player/agent identifiers found "
                    f"in configuration (expected in TOML 'agents' list)."
                )
                sys.exit(1)

            game = get_game_from_factory(game_factory_to_use, actual_player_names_for_game)
            logger.info(
                f"Game created using factory: {game_factory_to_use}. "
                f"Agent Identifiers: {actual_player_names_for_game}"
            )
        else:
            game = Game()
            logger.info(
                "Standard game created (no game factory specified). "
                "All game powers must be mapped by the agent configurations."
            )

        config.game_instance = game

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

        await orchestrator.run_game_loop(game, game_history)

    except KeyboardInterrupt:
        logger.info("Game interrupted by user (KeyboardInterrupt). Saving partial results...")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the game: {e}", exc_info=True)
        detailed_error = traceback.format_exc()
        logger.error(f"Detailed traceback:\n{detailed_error}")
    finally:
        if game and game_history and agent_manager:
            process_game_results(config, game, game_history, agent_manager, start_time)
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
