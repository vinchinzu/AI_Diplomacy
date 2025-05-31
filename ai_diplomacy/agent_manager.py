"""
Manages the creation, initialization, and storage of DiplomacyAgents.
"""
import logging
from typing import List, Dict, TYPE_CHECKING, Optional # Added Optional for get_agent return

from .agents.factory import AgentFactory
from .agents.base import BaseAgent
from .services.config import AgentConfig
from .model_utils import assign_models_to_powers # Import the new function

if TYPE_CHECKING:
    from .game_config import GameConfig

logger = logging.getLogger(__name__)

__all__ = ["AgentManager"]

# DEFAULT_AGENT_MANAGER_FALLBACK_MODEL has been moved to model_utils.py

class AgentManager:
    # Docstring already exists and is good.

    def __init__(self, game_config: "GameConfig"):
        """
        Initializes the AgentManager.

        Args:
            game_config: The game configuration object.
        """
        self.game_config = game_config
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_factory = AgentFactory()
        logger.info("AgentManager initialized.")

    def assign_models(self, all_game_powers: List[str]) -> Dict[str, str]:
        """
        Assigns LLM model IDs to each participating power in the game.

        This method considers:
        - A specific power controlled by a specific model (from config.power_name & config.model_id).
        - A list of fixed models to be assigned to other powers (from config.fixed_models).
        - Randomization of fixed model assignments (config.randomize_fixed_models).
        - Powers to be excluded (config.exclude_powers).
        - The total number of LLM-controlled players (config.num_players).

        Args:
            all_game_powers: A list of all power names in the game (e.g., ["AUSTRIA", "ENGLAND", ...]).

        Returns:
            A dictionary mapping power names to their assigned model IDs.
        """
        logger.info("Assigning models to powers...") # Kept initial logging

        # Call the new utility function
        final_llm_assignments = assign_models_to_powers(
            game_config=self.game_config,
            all_game_powers=all_game_powers,
        )

        # Store in game_config as well
        self.game_config.powers_and_models = final_llm_assignments
        logger.info( # Added a log message here for clarity on what AgentManager is doing
            f"AgentManager stored final model assignments from model_utils: {final_llm_assignments}"
        )
        return final_llm_assignments

    def _initialize_agent_state_ext(self, agent: BaseAgent):
        """
        Initializes extended state for an agent (e.g., loading from files, specific heuristics).
        This method is a placeholder for more complex setup that might be needed in the future.
        """
        logger.debug(
            f"Performing extended state initialization for {agent.country} (currently minimal)."
        )
        # This function can be expanded if there's a need to load specific initial states
        # from files or apply more complex power-specific heuristics here.
        pass

    def initialize_agents(self, powers_and_models: Dict[str, str]):
        """
        Creates and initializes agent instances for each power using the new factory system.

        Args:
            powers_and_models: A dictionary mapping power names to their assigned model IDs.
        """
        logger.info("Initializing agents...")
        self.agents = {}  # Clear any previous agents

        for power_name, model_id_for_power in powers_and_models.items():
            logger.info(
                f"Creating agent for {power_name} with model {model_id_for_power}"
            )
            try:
                # Create agent configuration
                agent_config = AgentConfig(
                    country=power_name,
                    type="llm",
                    model_id=model_id_for_power,
                    context_provider="auto",  # Will auto-select based on model capabilities
                    verbose_llm_debug=self.game_config.args.verbose_llm_debug if hasattr(self.game_config.args, 'verbose_llm_debug') else False # Pass verbose_llm_debug
                )

                # Create agent using factory
                agent_id = f"{power_name.lower()}_{self.game_config.game_id}"
                agent = self.agent_factory.create_agent(
                    agent_id=agent_id,
                    country=power_name,
                    config=agent_config,
                    game_id=self.game_config.game_id,
                )

                self._initialize_agent_state_ext(agent)  # Call extended initializer
                self.agents[power_name] = agent
                logger.info(f"Agent for {power_name} created and initialized.")
            except Exception as e:
                logger.error(
                    f"Failed to create or initialize agent for {power_name} with model {model_id_for_power}: {e}",
                    exc_info=True,
                )
                # Continue with other agents

        # Store in game_config as well
        self.game_config.agents = self.agents
        logger.info(f"All {len(self.agents)} agents initialized.")

    def get_agent(self, power_name: str) -> Optional[BaseAgent]:
        """
        Retrieves an initialized agent by its power name.

        Args:
            power_name: The name of the power whose agent is to be retrieved.

        Returns:
            The BaseAgent instance, or None if not found.
        """
        return self.agents.get(power_name)
