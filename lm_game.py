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
        default=None,
        help="Path to a TOML file containing game configuration. CLI arguments will override TOML settings.",
    )

    parser.add_argument(
        "--game_id_prefix",
        type=str,
        default=None,
        help="Prefix for the game ID if not explicitly set via --game_id or in TOML. Default: 'diplomacy_game'.",
    )
    parser.add_argument(
        "--game_id",
        type=str,
        default=None,
        help="Specific game ID to use. Overrides TOML or generated ID. Default: None.",
    )
    parser.add_argument(
        "--log_level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level. Overrides TOML. Default: INFO.",
    )
    parser.add_argument(
        "--log_to_file",
        type=lambda x: (str(x).lower() == "true"),
        default=None,
        help="Enable/disable file logging. Overrides TOML. Default: True (unless dev_mode).",
    )
    parser.add_argument(
        "--log_dir",
        type=str,
        default=None,
        help="Base directory for logs. Overrides TOML. Game-specific subfolder will be created here. Default: './logs'.",
    )
    parser.add_argument(
        "--max_years",
        type=int,
        default=None,
        help="Override max_years from TOML for a quick test.",
    )
    parser.add_argument(
        "--max_phases",
        type=int,
        default=None,
        help="Override max_phases from TOML for a quick test.",
    )
    parser.add_argument(
        "--perform_planning_phase",
        type=lambda x: (str(x).lower() == "true"),
        default=None,
        help="Override perform_planning_phase from TOML.",
    )
    parser.add_argument(
        "--num_negotiation_rounds",
        type=int,
        default=None,
        help="Override num_negotiation_rounds from TOML.",
    )

    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Specify a scenario name (e.g., wwi_two_player). This may override game_factory_path.",
    )

    return parser.parse_args()


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


async def main():
    args = parse_arguments()

    if args.scenario == "wwi_two_player":
        args.game_factory_path = "scenarios:wwi_two_player"
        logger.info(
            f"WWI two player scenario specified. Setting game_factory_path to '{args.game_factory_path}'."
        )

    if getattr(args, "llm_models", None) and isinstance(args.llm_models, str):
        args.llm_models_list = [m.strip() for m in args.llm_models.split(",")]
    else:
        args.llm_models_list = getattr(args, "llm_models_list", [])

    if getattr(args, "fixed_models", None) and isinstance(args.fixed_models, str):
        args.fixed_models_list = [m.strip() for m in args.fixed_models.split(",")]
    elif not hasattr(args, "fixed_models_list"):
        args.fixed_models_list = []

    if getattr(args, "players", None) and isinstance(args.players, str):
        args.players_list = [p.strip() for p in args.players.split(",")]
    else:
        args.players_list = getattr(args, "players_list", [])

    if getattr(args, "agent_types", None) and isinstance(args.agent_types, str):
        args.agent_types_list = [t.strip().lower() for t in args.agent_types.split(",")]
    else:
        args.agent_types_list = getattr(args, "agent_types_list", [])

    if getattr(args, "bloc_definitions", None) and isinstance(args.bloc_definitions, str):
        args.bloc_definitions_list = [d.strip() for d in args.bloc_definitions.split(",")]
    else:
        args.bloc_definitions_list = getattr(args, "bloc_definitions_list", [])

    if getattr(args, "exclude_powers", None) and isinstance(args.exclude_powers, str):
        args.exclude_powers_list = [p.strip().upper() for p in args.exclude_powers.split(",")]
    else:
        args.exclude_powers_list = getattr(args, "exclude_powers_list", [])

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

        agent_configurations: Dict[str, Dict[str, Any]] = {}
        actual_player_names_for_game: List[str] = []

        if config.players_list and config.agent_types_list:
            if len(config.players_list) != len(config.agent_types_list) or (
                config.llm_models_list
                and len(config.players_list) != len(config.llm_models_list)
                and any(at in ["llm", "bloc_llm"] for at in config.agent_types_list)
            ):
                llm_agent_count = sum(1 for at in config.agent_types_list if at in ["llm", "bloc_llm"])
                if config.llm_models_list and len(config.llm_models_list) < llm_agent_count:
                    logger.error(
                        "Mismatch in number of elements for --players, --agent-types, or insufficient --llm-models. "
                        f"Players: {len(config.players_list)}, Types: {len(config.agent_types_list)}, Models: {len(config.llm_models_list)} (needed for {llm_agent_count} LLM agents)."
                    )
                    sys.exit(1)

            actual_player_names_for_game = config.players_list
            llm_models_to_use = config.llm_models_list or config.fixed_models or []
            llm_model_idx = 0

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
                            f"AgentManager might fail if it's required. Player identifier '{player_identifier}' will be used as fallback."
                        )
                        current_agent_setup["country"] = player_identifier
                elif agent_type == "bloc_llm":
                    current_agent_setup["bloc_name"] = player_identifier
                    if player_identifier in parsed_bloc_defs:
                        current_agent_setup["controlled_powers"] = parsed_bloc_defs[player_identifier]
                    else:
                        logger.error(
                            f"No definition found for bloc: {player_identifier}. Ensure it is defined in TOML or CLI. Skipping."
                        )
                        continue
                elif agent_type == "human":
                    current_agent_setup["country"] = player_identifier
                    logger.info(
                        f"Human player defined: {player_identifier}. Manual control assumed. Skipping agent creation via AgentManager."
                    )
                    continue
                else:
                    logger.warning(
                        f"Unknown agent type: {agent_type} for player {player_identifier}. Skipping."
                    )
                    continue
                agent_configurations[player_identifier] = current_agent_setup

        if not agent_configurations:
            logger.error(
                "No agent configurations were created. "
                "Please ensure agent definitions are provided via a TOML config file (in the 'agents' list) "
                "or via comprehensive command-line player/agent arguments."
            )
            sys.exit(1)

        game_factory_to_use = config.game_factory_path

        if game_factory_to_use:
            if not actual_player_names_for_game and "wwi_two_player" not in game_factory_to_use:
                logger.error(
                    f"Game factory '{game_factory_to_use}' specified, but no player/agent identifiers found in configuration "
                    f"(expected in TOML 'agents' list or via CLI)."
                )
                sys.exit(1)

            game = get_game_from_factory(game_factory_to_use, actual_player_names_for_game)
            logger.info(
                f"Game created using factory: {game_factory_to_use}. Agent Identifiers involved: {actual_player_names_for_game}"
            )
        else:
            game = Game()
            logger.info(
                "Standard game created (no game factory specified in configuration)."
                " All game powers must be mapped by the agent configurations provided."
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
            logger.info("Game loop finished or interrupted. Processing final results...")
            results_processor = GameResultsProcessor(config)
            results_processor.log_final_results(game)
            if config.log_to_file:
                results_processor.save_game_state(game, game_history)
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
