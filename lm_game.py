import logging
import time
from typing import Optional

from ai_diplomacy.game_config import GameConfig, load_game_config
from ai_diplomacy.game_state import GameState
from ai_diplomacy.runtime import GameRunner
from ai_diplomacy.runtime.agents import initialize_agents
from ai_diplomacy.utils import (
    get_all_powers_for_game,
    get_manifesto_powers,
    setup_logging,
    write_manifestos_to_file,
)

logger = logging.getLogger(__name__)


def run_game(args):
    if args.report_imbalances:
        logger.info("Reporting power imbalances and exiting without running game.")
        return

    config: GameConfig = load_game_config(args.scenario, args)

    agent_configurations = config.scenario_data.get("agents", {})
    if not agent_configurations:
        raise ValueError("No agent configurations found in the scenario file.")

    initialize_agents(config, agent_configurations)

    game_runner = GameRunner(config, game)
    game_runner.run_game_loop()

    logger.info("Game simulation finished.")
    if config.agents:
        logger.info("Finalizing agents and saving manifestos...")
        try:
            manifesto_powers = get_manifesto_powers(config.agents)
            write_manifestos_to_file(
                config.game_id,
                manifesto_powers,
                config.agents,
                config.output_dir,
            )
        except Exception as e:
            logger.error(f"Error saving manifestos: {e}", exc_info=True)


def save_agent_manifestos(
    config: GameConfig,
):
    if not config.agents:
        logger.warning("AgentManager agents not initialized, skipping manifesto saving.")
        return

    manifesto_powers = get_manifesto_powers(config.agents)
    write_manifestos_to_file(
        config.game_id,
        manifesto_powers,
        config.agents,
        config.output_dir,
    )


def _setup_and_run_game(
    args,
    game: GameState,
    game_id: Optional[str] = None,
    game_config: Optional[GameConfig] = None,
    agent_manager: Optional[AgentManager] = None
):
    """Core game setup and execution logic, shared by different entry points."""
    if not game_config:
        game_config = load_game_config(args.scenario, args, game_id_override=game_id)

    if not agent_manager:
        agent_manager = AgentManager(game_config)
        agent_configurations = game_config.scenario_data.get("agents", {})
        agent_manager.initialize_agents(agent_configurations)

    game_runner = GameRunner(game_config, game)
    game_runner.run_game_loop()
    return game_runner


def main():
    """Main entry point for running a game from a scenario file."""
    # This function will be expanded to handle command-line argument parsing
    # and setting up the game based on those arguments.
    pass

    # ... existing code ...

    # ... rest of the existing code ... 