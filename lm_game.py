import argparse
import asyncio
import logging
import os
import sys  # For sys.exit
import importlib  # For dynamically importing game factory

_project_root_dir = os.path.dirname(os.path.abspath(__file__))
if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

import time  
import traceback  # For exception logging
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
        "--game_config_file", "--config",
        type=str,
        default=None,
        help="Path to a TOML file containing game configuration. CLI arguments will override TOML settings."
    )

    parser.add_argument(
        "--game_id",
        type=str,
        default=None,
        help="Specific game ID to use. Overrides TOML or generated ID. Default: None.",
    )
    # Keep a few for direct overrides if needed, like max_years for a quick test.
    parser.add_argument("--max_years", type=int, default=None, help="Override max_years from TOML for a quick test.")
    parser.add_argument("--perform_planning_phase", type=lambda x: (str(x).lower() == "true"), default=None, help="Override perform_planning_phase from TOML.")
    parser.add_argument("--num_negotiation_rounds", type=int, default=None, help="Override num_negotiation_rounds from TOML.")
    parser.add_argument(
        "--fixed_models",
        type=str,
        default=None,
        help="Comma-separated list of model IDs to assign to agents, overriding TOML models. Order corresponds to LLM agents."
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
            return factory_func(
                entente_player=player_names[0],
                central_player=player_names[1],
                italy_controller="NEUTRAL_ITALY",
            )
        else:
            # Fallback for other factories or incorrect player count for wwi_2p
            # This part might need adjustment depending on other factory signatures
            logger.warning(
                f"Generic factory call for {factory_path}. Ensure player_names match factory needs."
            )
            return factory_func(
                *player_names
            )  # Or however generic factories are called
    except (ImportError, AttributeError, TypeError) as e:
        logger.error(f"Error loading game factory '{factory_path}': {e}", exc_info=True)
        raise


async def main():
    args = parse_arguments()

    # Pass the raw args to GameConfig. GameConfig is responsible for interpreting them,
    # including loading from TOML and applying CLI overrides.
    config = GameConfig(args)
    setup_logging(config)

    logger.info(f"Starting Diplomacy game: {config.game_id}")
    # Log the lists directly from the config object.
    # These attributes are populated by GameConfig from TOML or CLI overrides.
    if config.players: # 'players' is the attribute in GameConfig that holds the list of agent identity objects
        logger.info(f"Players/Agents (from config): {[agent.id for agent in config.players]}") # Example: log agent IDs
        # Depending on how GameConfig stores these, you might log different attributes.
        # For example, if GameConfig directly creates players_list, agent_types_list:
        if hasattr(config, 'players_list') and config.players_list:
             logger.info(f"Players List (from config): {config.players_list}")
        if hasattr(config, 'agent_types_list') and config.agent_types_list:
            logger.info(f"Agent Types List (from config): {config.agent_types_list}")
        if hasattr(config, 'bloc_definitions_map') and config.bloc_definitions_map: # Assuming it's parsed into a map
            logger.info(f"Bloc Definitions (from config): {config.bloc_definitions_map}")
        if hasattr(config, 'llm_models_list') and config.llm_models_list:
            logger.info(f"LLM Models List (from config): {config.llm_models_list}")
    # logger.info(f"Fixed Models (from config): {config.fixed_models}") # This would be how fixed_models is stored

    start_time = time.time()

    game: Optional[Game] = None
    game_history: Optional[GameHistory] = None
    agent_manager: Optional[AgentManager] = None

    try:
        game_history = GameHistory()
        agent_manager = AgentManager(config)

        # Construct agent_configurations using the new method in GameConfig
        try:
            agent_configurations = config.build_agent_configurations()
        except ValueError as e:
            logger.error(f"Error building agent configurations: {e}")
            sys.exit(1)
        
        # actual_player_names_for_game should be derived from the keys of agent_configurations 
        # or directly from config.players_list, which is the list of agent IDs.
        # config.players_list is more direct if it's guaranteed to be the list of *active* agent IDs.
        # The keys of agent_configurations will only contain successfully built agents.
        actual_player_names_for_game: List[str] = list(agent_configurations.keys())
        # Or, if you need the original list from TOML (which might include agents that failed to build):
        # actual_player_names_for_game: List[str] = config.players_list


        # Agent definitions are now mandatory via TOML. GameConfig's build_agent_configurations
        # will raise an error or return an empty dict if no valid agents are found/built.
        if not agent_configurations:
            logger.error(
                "No agent configurations were successfully created by GameConfig. "
                "Please ensure agent definitions are provided and correct in the TOML config file."
            )
            sys.exit(1)

        # Create Game Instance
        game_factory_to_use = config.game_factory_path 

        if game_factory_to_use:
            # actual_player_names_for_game is now list(agent_configurations.keys())
            # These IDs are agent identifiers (power names, bloc names, etc.)
            if not actual_player_names_for_game and "wwi_two_player" not in game_factory_to_use:
                logger.error(
                    f"Game factory '{game_factory_to_use}' specified, but no player/agent identifiers could be prepared from configuration. "
                    f"(Expected valid agent definitions in TOML 'agents' list)."
                )
                sys.exit(1)
            
            # If actual_player_names_for_game is empty here, and it's not wwi_two_player,
            # it means no agents were successfully configured, which should have been caught above.
            # However, get_game_from_factory might need a list of specifically *player* names,
            # which config.players_list provides directly.
            # Using config.players_list here aligns with the original intent if the factory
            # needs all *defined* players, not just successfully configured ones.
            # Let's use config.players_list as it's the direct list of defined agent IDs.
            game = get_game_from_factory(
                game_factory_to_use, config.players_list # Use the original list of player IDs from config
            )
            logger.info(
                f"Game created using factory: {game_factory_to_use}. Agent Identifiers involved (from config.players_list): {config.players_list}"
            )
        else:
            game = Game()
            logger.info("Standard game created (no game factory specified in configuration)."
                        " All game powers must be mapped by the agent configurations provided.")

        config.game_instance = game 

        logger.info(f"Final agent configurations (built by GameConfig) to be initialized: {agent_configurations}")
        agent_manager.initialize_agents(agent_configurations)

        if not agent_manager.agents:
            logger.error("Failed to initialize any agents. Exiting.")
            sys.exit(1)

        # Build and validate agent maps
        try:
            config.build_and_validate_agent_maps(
                game_instance=game,
                agent_configurations=agent_configurations,
                initialized_agents=agent_manager.agents
            )
        except ValueError as e:
            logger.error(f"Game setup validation failed: {e}")
            sys.exit(1)

        # Reconstruct powers_and_models for compatibility if needed by PhaseOrchestrator
        # This map associates each individual game power with its controlling model ID.
        powers_and_models_map: Dict[str, str] = {}
        for agent_id, agent_config_details in agent_configurations.items():
            model_id = agent_config_details.get("model_id")
            # Check if this agent_id is in the validated agent_to_powers_map
            if agent_id in config.agent_to_powers_map and model_id:
                for power_name in config.agent_to_powers_map[agent_id]:
                    # Ensure the power is part of the current game (already validated by build_and_validate_agent_maps)
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
        logger.info(
            "Game interrupted by user (KeyboardInterrupt). Saving partial results..."
        )
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during the game: {e}", exc_info=True
        )
        detailed_error = traceback.format_exc()
        logger.error(f"Detailed traceback:\n{detailed_error}")
    finally:
        if game and game_history and agent_manager:
            logger.info(
                "Game loop finished or interrupted. Processing final results..."
            )
            results_processor = GameResultsProcessor(config)  # config now holds args
            results_processor.log_final_results(game)
            if config.log_to_file:  # Access log_to_file via config itself
                results_processor.save_game_state(game, game_history)
                if agent_manager.agents:
                    results_processor.save_agent_manifestos(
                        agent_manager.agents
                    )  # Pass dict of agents
                else:
                    logger.warning(
                        "AgentManager agents not initialized, skipping manifesto saving."
                    )
            logger.info(
                f"Results processing complete. Total game time: {time.time() - start_time:.2f} seconds."
            )
            logger.info(
                f"Output files are located in: {config.game_id_specific_log_dir}"
            )
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
        initial_logger.error(
            f"Critical error in asyncio.run(main()): {e}", exc_info=True
        )
        detailed_traceback = traceback.format_exc()
        initial_logger.error(f"Detailed traceback:\n{detailed_traceback}")
        sys.exit(1)
