# pragma: no cover
import argparse
import asyncio
import logging
import os
import sys
from typing import Dict, Any, List

# Ensure the project root is in sys.path
_project_root_dir = os.path.dirname(os.path.abspath(__file__))
if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

from diplomacy import Game
import dotenv

from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.orchestrators.phase_orchestrator import PhaseOrchestrator
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.general_utils import get_valid_orders  # Or determine if still needed
import scenarios  # For wwi_two_player
from ai_diplomacy import constants  # Added import

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

# Define the bloc names and their constituent powers
ENTENTE_BLOC_NAME = "ENTENTE_POWERS"
CENTRAL_BLOC_NAME = "CENTRAL_POWERS"
ITALY_BLOC_NAME = "NEUTRAL_ITALY_BLOC"  # Matches scenarios.py

WWI_BLOC_MAP = {
    ENTENTE_BLOC_NAME: ["ENGLAND", "FRANCE", "RUSSIA"],
    CENTRAL_BLOC_NAME: ["AUSTRIA", "GERMANY", "TURKEY"],
    ITALY_BLOC_NAME: [
        "ITALY"
    ],  # Italy is initially neutral, controlled by its own bloc conceptually
}


async def run_wwi_scenario():
    """Runs the WWI two-player scenario."""
    # 1. Setup Configuration: Now primarily driven by a TOML file.
    # CLI arguments can override TOML settings.
    parser = argparse.ArgumentParser(description="WWI Diplomacy Test Scenario Runner")
    parser.add_argument(
        "--config", "--game_config_file",
        dest="game_config_file", # Explicitly set destination attribute name
        type=str,
        default="wwi_scenario.toml", # Default to the local WWI scenario TOML
        help="Path to a TOML file containing game configuration."
    )
    # Add any other CLI args you might want to allow for overriding TOML specifically for this test
    parser.add_argument("--max_years", type=int, help="Override max_years from TOML.")
    parser.add_argument("--log_level", type=str, help="Override log_level from TOML.")
    # For this test, we assume other llm_game.py args are available if lm_game.parse_arguments was used
    # but for a standalone test script, explicitly define what can be overridden.

    # If this script is run directly, it needs to parse its own args.
    # If lm_game.py is the entry point and calls this, args would come from there.
    # For simplicity in this test, we'll parse limited args here.
    # A more integrated approach would have lm_game.py handle all parsing and pass full args.
    
    # Simulate a simplified args namespace for GameConfig, prioritizing CLI for overrides
    # This mimics what lm_game.py's parse_arguments() and _apply_preset_to_args() would do.
    cli_args = parser.parse_args()

    # Construct a base args namespace that lm_game.main expects GameConfig to receive.
    # GameConfig will handle loading from the TOML specified in cli_args.game_config_file.
    # It will also use any direct CLI overrides present in cli_args.
    # Essential fields for GameConfig that might not be in a minimal TOML or simple cli_args:
    args_for_game_config_dict = {
        "game_config_file": cli_args.game_config_file,
        "max_years": cli_args.max_years, # Will be None if not provided, TOML will take precedence
        "log_level": cli_args.log_level, # Same as above
        # Defaults for fields that lm_game.py's argparser would normally provide defaults for,
        # if not in TOML or overridden by specific CLI args for this script.
        "preset": None, # Presets are less relevant when using a full TOML config
        "game_factory": None, # Will be loaded from TOML by GameConfig
        "players": None, # Will be loaded from TOML's agent list by GameConfig
        "agent_types": None, # Loaded from TOML by GameConfig
        "bloc_definitions": None, # Loaded from TOML by GameConfig
        "llm_models": None, # Loaded from TOML by GameConfig
        "power_name": None,
        "model_id": None,
        "num_players": None, # GameConfig will derive from TOML agents or use default
        "game_id_prefix": "test_wwi_scenario", # Default for this test
        "game_id": None,
        "log_to_file": None, # GameConfig will decide based on TOML/CLI/dev_mode
        "log_dir": None,
        "perform_planning_phase": False,
        "num_negotiation_rounds": None, # Will be loaded from TOML
        "negotiation_style": "simultaneous",
        "fixed_models": None,
        "randomize_fixed_models": False,
        "exclude_powers": None,
        "dev_mode": False, # Explicit for test, can be in TOML
        "verbose_llm_debug": True, # Explicit for test, can be in TOML
        "max_diary_tokens": 6500,
        # Ensure *_list attributes are initialized as GameConfig might expect them from lm_game.py
        "players_list": [],
        "agent_types_list": [],
        "llm_models_list": [],
        "fixed_models_list": [],
        "bloc_definitions_list": [],
        "exclude_powers_list": [],
    }
    # Update with any actual CLI overrides provided to this script
    for key, value in vars(cli_args).items():
        if value is not None:
            args_for_game_config_dict[key] = value
            if key.endswith("_list") and isinstance(value, str): # e.g. if a list arg was added to this script
                 args_for_game_config_dict[key] = [v.strip() for v in value.split(",")]
            elif key == "fixed_models" and isinstance(value, str): # Special handling for fixed_models string
                 args_for_game_config_dict["fixed_models_list"] = [v.strip() for v in value.split(",")]


    args = argparse.Namespace(**args_for_game_config_dict)

    # GameConfig will now load from the TOML file specified in args.game_config_file
    # and apply any direct CLI overrides from `args`.
    config = GameConfig(args)
    setup_logging(config)
    logger.info(f"Starting WWI Diplomacy Test Scenario: {config.game_id}")
    logger.info(f"Using game config file: {config.game_config_file_path}")
    logger.info(f"Effective configuration after TOML and CLI processing: {vars(config)}") # Log the whole config

    game_history = GameHistory()
    game: Game

    # Game creation: GameConfig now holds game_factory_path from TOML
    if not config.game_factory_path:
        logger.error("Game factory path not found in configuration (TOML or CLI). Cannot create game.")
        raise ValueError("Missing game_factory_path in config.")

    # The agent IDs from TOML (e.g., ENTENTE_POWERS) are expected by wwi_two_player factory.
    # GameConfig.players_list should now contain these from the TOML 'agents' list.
    if not config.players_list or len(config.players_list) < 2:
        logger.error(f"Expected at least 2 player identifiers (bloc names) from TOML agents list for WWI scenario, found: {config.players_list}")
        # wwi_two_player factory has defaults, but good to ensure config drives this.
        # For this specific factory, it can run with defaults if players_list is empty, but we want to test TOML loading.
        # So, if we intended TOML to provide it, this is an issue.
        raise ValueError("Insufficient player/bloc identifiers in config.players_list for WWI scenario factory.")

    # Ensure game_instance is set on config *before* build_and_validate_agent_maps
    game = scenarios.wwi_two_player(
        entente_player=config.players_list[0], # Assumes order in TOML agents list is Entente, Central, Italy
        central_player=config.players_list[1],
        italy_controller=config.players_list[2] if len(config.players_list) > 2 else "ITALY_NEUTRAL" # Default if not in TOML
    )
    config.game_instance = game

    logger.info(
        f"WWI Game created with powers: {list(game.powers.keys())}. Metadata should reflect bloc names from TOML."
    )

    agent_manager = AgentManager(config)

    # Construct agent_configurations dictionary for AgentManager
    # This logic is now simplified as GameConfig provides the lists directly.
    agent_configurations: Dict[str, Dict[str, Any]] = {}
    if config.players_list and config.agent_types_list:
        # Model list should correspond to player list for llm/bloc_llm types
        llm_models_to_use = config.llm_models_list or config.fixed_models or []
        model_idx = 0
        parsed_bloc_defs: Dict[str, List[str]] = {}
        if config.bloc_definitions_list: # This list is already populated by GameConfig from TOML/CLI
            for bloc_def_str in config.bloc_definitions_list:
                parts = bloc_def_str.split(":", 1)
                if len(parts) == 2:
                    bloc_name_def, powers_str = parts
                    parsed_bloc_defs[bloc_name_def.strip()] = [p.strip().upper() for p in powers_str.split(";")]

        for i, agent_identifier in enumerate(config.players_list):
            agent_type = config.agent_types_list[i]
            current_agent_setup: Dict[str, Any] = {"type": agent_type}

            if agent_type in ["llm", "bloc_llm"]:
                if model_idx < len(llm_models_to_use) and llm_models_to_use[model_idx]:
                    current_agent_setup["model_id"] = llm_models_to_use[model_idx]
                else:
                    # If model list from TOML was shorter or had empty strings
                    logger.warning(f"No specific model found for {agent_type} agent '{agent_identifier}' at index {i} in llm_models_list. Agent may use a default or fail if model is required.")
                    current_agent_setup["model_id"] = None # Explicitly None
                model_idx +=1 # Increment even if model is None to keep alignment if some agents don't need models
            
            if agent_type == "llm":
                current_agent_setup["country"] = agent_identifier
            elif agent_type == "neutral":
                current_agent_setup["country"] = agent_identifier
            elif agent_type == "bloc_llm":
                current_agent_setup["bloc_name"] = agent_identifier
                # Powers for the bloc come from the 'powers' sub-field in TOML's agent entry,
                # which GameConfig used to create bloc_definitions_list, then parsed here into parsed_bloc_defs
                if agent_identifier in parsed_bloc_defs:
                    current_agent_setup["controlled_powers"] = parsed_bloc_defs[agent_identifier]
                else:
                    logger.error(f"Bloc '{agent_identifier}' defined in agents list but no matching definition in bloc_definitions. Check TOML.")
                    continue # Skip this misconfigured agent
            # Human players would be listed in TOML but usually not processed by AgentManager this way.
            # If a human type were in TOML and config.players_list, it would be skipped by AgentManager.initialize_agents
            
            agent_configurations[agent_identifier] = current_agent_setup
    else:
        logger.error("Could not construct agent_configurations: players_list or agent_types_list is empty in GameConfig.")
        raise RuntimeError("Failed to load agent definitions for WWI scenario.")


    logger.info(f"Constructed agent configurations for AgentManager: {agent_configurations}")
    agent_manager.initialize_agents(agent_configurations=agent_configurations)

    # Build and validate agent maps first. This will populate
    # config.power_to_agent_id_map and config.agent_to_powers_map.
    try:
        config.build_and_validate_agent_maps(
            game_instance=game,
            agent_configurations=agent_configurations,
            initialized_agents=agent_manager.agents
        )
    except ValueError as e:
        logger.error(f"WWI scenario game setup validation failed: {e}")
        raise RuntimeError(f"WWI scenario validation failed: {e}") from e

    # Reconstruct powers_and_models_map using the validated config.agent_to_powers_map.
    # This map should associate each individual game power with its controlling model ID.
    # NullAgents will be correctly excluded as they don't have a model_id.
    powers_and_models_map: Dict[str, str] = {}
    for agent_id, agent_config_details in agent_configurations.items():
        model_id = agent_config_details.get("model_id")
        # Check if this agent_id is in the validated agent_to_powers_map and has a model_id.
        if agent_id in config.agent_to_powers_map and model_id:
            for power_name in config.agent_to_powers_map[agent_id]:
                # The power_name is already validated to be in game.powers
                powers_and_models_map[power_name] = model_id
    
    config.powers_and_models = powers_and_models_map
    logger.info(f"Reconstructed config.powers_and_models: {config.powers_and_models}")

    # config.power_to_agent_id_map is already populated and validated by build_and_validate_agent_maps
    logger.info(f"Validated config.power_to_agent_id_map: {config.power_to_agent_id_map}")
    logger.info(f"Validated config.agent_to_powers_map: {config.agent_to_powers_map}")

    # The check for number of agents should now compare against the number of agent_configurations keys
    if not agent_manager.agents or len(agent_manager.agents) != len(agent_configurations):
        logger.error(
            f"Failed to initialize all agents. Expected: {len(agent_configurations)}, Got: {len(agent_manager.agents) if agent_manager.agents else 0}. Agents: {list(agent_manager.agents.keys())}"
        )
        # Consider raising an exception here
        raise RuntimeError("Failed to initialize all required agents.")
    logger.info(f"Agents initialized: {list(agent_manager.agents.keys())}")

    orchestrator = PhaseOrchestrator(
        game_config=config,
        agent_manager=agent_manager,
        get_valid_orders_func=get_valid_orders,
    )

    logger.info("Starting game loop...")
    # Removed the try...except Exception as e block here to let errors propagate
    await orchestrator.run_game_loop(game, game_history)

    # This part will only be reached if run_game_loop completes without unhandled exceptions
    logger.info("Game loop finished.")
    if game.is_game_done:
        # game.get_winning_powers() might be available in some diplomacy library versions
        # but game.phase should indicate 'COMPLETED' or similar, and draws are common.
        winners = []
        if hasattr(game, "get_winning_powers"):
            winners = game.get_winning_powers()  # type: ignore

        if winners:
            logger.info(f"Game finished. Winners: {winners}. Final phase: {game.phase}")
        elif (
            game.phase == constants.GAME_STATUS_COMPLETED
        ):  # Check against a constant if available
            logger.info(
                f"Game completed (likely a draw or reached max years). Final phase: {game.phase}"
            )
        else:
            logger.info(
                f"Game finished. No explicit winners. Final phase: {game.phase}"
            )
    else:
        logger.info(f"Game ended prematurely. Current phase: {game.phase}")


if __name__ == "__main__":
    try:
        asyncio.run(run_wwi_scenario())
    except Exception as e:
        # This top-level catch is okay for logging the final crash reason before exit
        logger.error(f"Critical error running WWI scenario: {e}", exc_info=True)
        sys.exit(1)  # Ensure script exits with an error code
    logger.info("WWI Scenario script finished successfully.")
