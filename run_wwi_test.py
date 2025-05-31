import argparse
import asyncio
import logging
import os
import sys

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
from ai_diplomacy.general_utils import get_valid_orders # Or determine if still needed
import scenarios # For wwi_two_player
from ai_diplomacy import constants # Added import

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

# Define the bloc names and their constituent powers
ENTENTE_BLOC_NAME = "ENTENTE_POWERS"
CENTRAL_BLOC_NAME = "CENTRAL_POWERS"
ITALY_BLOC_NAME = "NEUTRAL_ITALY_BLOC" # Matches scenarios.py

WWI_BLOC_MAP = {
    ENTENTE_BLOC_NAME: ["ENGLAND", "FRANCE", "RUSSIA"],
    CENTRAL_BLOC_NAME: ["AUSTRIA", "GERMANY", "TURKEY"],
    ITALY_BLOC_NAME: ["ITALY"] # Italy is initially neutral, controlled by its own bloc conceptually
}

async def run_wwi_scenario():
    """Runs the WWI two-player scenario."""
    # 1. Setup Configuration (Simplified for this test script)
    args_dict = {
        "preset": "wwi_2p", # This helps if GameConfig uses it, but we'll be more explicit
        "game_factory": "scenarios:wwi_two_player",
        "players": "llm,llm,llm", # Representing Entente, Central, and Neutral Italy blocs
        #"llm_models": "gemma3:12b,gemma3:12b,gemma3:12b", # One model for Entente, one for Central, one for Italy
        "llm_models": "gemma3:4b,gemma3:4b,gemma3:4b", # One model for Entente, one for Central, one for Italy
        "log_level": "DEBUG",
        "log_to_file": True,
        "log_dir": None, # GameConfig will use default ./logs
        "game_id_prefix": "test_wwi_scenario",
        "max_years": 1902, # Run for a short period for testing
        "num_negotiation_rounds": 0,
        # Add any other essential args GameConfig expects or presets would set
        "num_players": 3, # Number of conceptual players/blocs
        "fixed_models": None, # Covered by llm_models
        "game_id": None,
        "perform_planning_phase": False,
        "negotiation_style": "simultaneous",
        "randomize_fixed_models": False,
        "exclude_powers": None,
        "power_name": None,
        "model_id": None,
        "verbose_llm_debug": True, # Added for verbose LLM logging
    }
    args = argparse.Namespace(**args_dict)

    config = GameConfig(args)
    setup_logging(config)
    logger.info(f"Starting WWI Diplomacy Test Scenario: {config.game_id}")
    logger.info(f"Full configuration: {vars(config.args)}")

    game_history = GameHistory()
    game: Game

    game = scenarios.wwi_two_player(
        entente_player=ENTENTE_BLOC_NAME,
        central_player=CENTRAL_BLOC_NAME,
        italy_controller=ITALY_BLOC_NAME
    )
    logger.info(f"WWI Game created with powers: {list(game.powers.keys())}. Metadata should reflect bloc names.")
    config.game_instance = game

    agent_manager = AgentManager(config)

    actual_powers_to_models: Dict[str, str] = {}
    # Ensure llm_models is treated as a string before split, as it comes from args_dict
    llm_models_str = args.llm_models if isinstance(args.llm_models, str) else ""
    model_list = llm_models_str.split(',') if llm_models_str else []

    if len(model_list) < 3:
        logger.error(f"Insufficient LLM models provided. Expected 3, got {len(model_list)}. Models: {args.llm_models}")
        return # Exit if not enough models

    bloc_models = {
        ENTENTE_BLOC_NAME: model_list[0],
        CENTRAL_BLOC_NAME: model_list[1],
        ITALY_BLOC_NAME: model_list[2],
    }

    for bloc_name, member_powers in WWI_BLOC_MAP.items():
        model_for_bloc = bloc_models.get(bloc_name)
        if model_for_bloc:
            for power_name in member_powers:
                if power_name in game.powers:
                    actual_powers_to_models[power_name] = model_for_bloc.strip()
        else:
            logger.error(f"No model defined for bloc: {bloc_name}")
            # Consider raising an exception here to halt execution if this is critical
            raise ValueError(f"No model defined for critical bloc: {bloc_name}")

    if not actual_powers_to_models or len(actual_powers_to_models) != len(game.powers):
        logger.error(
            f"Failed to create a complete mapping from actual powers to models. Mapped: {actual_powers_to_models}. Game powers: {list(game.powers.keys())}"
        )
        # Consider raising an exception here
        raise ValueError("Incomplete power-to-model mapping.")

    logger.info(f"Initializing agents for actual powers: {actual_powers_to_models}")
    agent_manager.initialize_agents(powers_and_models=actual_powers_to_models)
    config.powers_and_models = actual_powers_to_models

    if not agent_manager.agents or len(agent_manager.agents) != len(game.powers):
        logger.error(f"Failed to initialize all agents. Expected: {len(game.powers)}, Got: {len(agent_manager.agents) if agent_manager.agents else 0}")
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
        if hasattr(game, 'get_winning_powers'):
            winners = game.get_winning_powers() # type: ignore
        
        if winners:
            logger.info(f"Game finished. Winners: {winners}. Final phase: {game.phase}")
        elif game.phase == constants.GAME_STATUS_COMPLETED: # Check against a constant if available
            logger.info(f"Game completed (likely a draw or reached max years). Final phase: {game.phase}")
        else:
            logger.info(f"Game finished. No explicit winners. Final phase: {game.phase}")
    else:
        logger.info(f"Game ended prematurely. Current phase: {game.phase}")


if __name__ == "__main__":
    try:
        asyncio.run(run_wwi_scenario())
    except Exception as e:
        # This top-level catch is okay for logging the final crash reason before exit
        logger.error(f"Critical error running WWI scenario: {e}", exc_info=True)
        sys.exit(1) # Ensure script exits with an error code
    logger.info("WWI Scenario script finished successfully.") 