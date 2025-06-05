"""
Manages the creation, initialization, and storage of DiplomacyAgents.
"""

import logging
from typing import Dict, TYPE_CHECKING, Optional, Any  # Added Any

from .agents.factory import AgentFactory
from .agents.base import BaseAgent
from .services.config import AgentConfig  # AgentConfig from services

if TYPE_CHECKING:
    from .game_config import GameConfig  # GameConfig from root

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
        self.agents: Dict[
            str, BaseAgent
        ] = {}  # Keyed by agent identifier (power name or bloc name)
        self.agent_factory = AgentFactory(
            # Pass coordinator and factory if they are part of game_config or globally managed
            # For now, assume AgentFactory default constructor is sufficient or it gets them from elsewhere.
        )
        logger.info("AgentManager initialized.")

    # The assign_models method is removed/commented out as its core logic
    # (determining which power gets which model) will be handled upstream
    # before initialize_agents is called. The new `agent_configurations`
    # argument to initialize_agents will carry this information.

    def _initialize_agent_state_ext(self, agent: BaseAgent):
        """
        Initializes extended state for an agent (e.g., loading from files, specific heuristics).
        This method is a placeholder for more complex setup that might be needed in the future.
        """
        logger.debug(
            f"Performing extended state initialization for {agent.agent_id} (currently minimal)."
        )
        # This function can be expanded if there's a need to load specific initial states
        # from files or apply more complex power-specific heuristics here.
        pass

    def initialize_agents(
        self,
        agent_configurations: Dict[str, Dict[str, Any]],
    ):
        """
        Creates and initializes agent instances based on provided configurations.

        Args:
            agent_configurations: A dictionary where keys are agent identifiers
                (e.g., "FRANCE" or "ENTENTE_BLOC") and values are dictionaries
                containing agent setup details like type, model_id, country (for single),
                bloc_name, controlled_powers (for blocs).
        """
        logger.info(
            f"Initializing agents based on configurations: {list(agent_configurations.keys())}"
        )
        self.agents = {}  # Clear any previous agents

        for agent_identifier, config_details in agent_configurations.items():
            agent_type = config_details.get("type")
            model_id = config_details.get("model_id")  # Can be None for neutral

            # Construct AgentConfig for the factory
            # The factory's create_agent expects an AgentConfig object.
            # We need to map our config_details to this.
            # AgentConfig fields: country, type, model_id, etc.
            # For bloc agents, 'country' in AgentConfig might be the bloc_name or a primary power.
            # Let's use agent_identifier for 'country' field in AgentConfig for now.

            # verbose_llm_debug should come from game_config
            verbose_llm_debug = getattr(
                self.game_config.args, "verbose_llm_debug", False
            )

            # Create the specific AgentConfig instance for the agent/bloc
            # The 'country' field in AgentConfig is a bit ambiguous for blocs.
            # The factory's create_agent uses it for single agents.
            # For bloc agents, bloc_name and controlled_powers are passed separately.
            # Let's set AgentConfig.country to be the primary identifier from the loop.
            current_agent_config = AgentConfig(
                country=agent_identifier,  # "FRANCE" or "ENTENTE_BLOC"
                type=agent_type,
                model_id=model_id,
                # Other fields like temperature, context_provider can be added from game_config.args if needed
                verbose_llm_debug=verbose_llm_debug,
            )

            agent_id_str = f"{agent_identifier.lower().replace(' ', '_')}_{self.game_config.game_id}"

            logger.info(
                f"Creating agent for '{agent_identifier}' of type '{agent_type}' with model '{model_id if model_id else 'N/A'}'"
            )

            try:
                agent: Optional[BaseAgent] = None
                if agent_type == "llm":
                    agent = self.agent_factory.create_agent(
                        agent_id=agent_id_str,
                        country=config_details.get(
                            "country", agent_identifier
                        ),  # Actual game power name
                        config=current_agent_config,
                        game_id=self.game_config.game_id,
                    )
                elif agent_type == "neutral":
                    agent = self.agent_factory.create_agent(
                        agent_id=agent_id_str,
                        country=config_details.get(
                            "country", agent_identifier
                        ),  # Actual game power name
                        config=current_agent_config,  # type="neutral"
                        game_id=self.game_config.game_id,
                    )
                elif agent_type == "null":
                    power_name_for_null = config_details.get("country", agent_identifier)
                    # NullAgent is not created via factory, but directly
                    from .agents.null_agent import NullAgent # Ensure NullAgent is imported
                    agent = NullAgent(
                        agent_id=agent_id_str, # agent_identifier could be "ITALY_NULL" or similar
                        game_config=self.game_config,
                        power_name=power_name_for_null # The actual power like "ITALY"
                    )
                    logger.info(f"Directly instantiating NullAgent for power: {power_name_for_null}")
                elif agent_type == "bloc_llm":
                    bloc_name = config_details.get("bloc_name", agent_identifier)
                    controlled_powers = config_details.get("controlled_powers")
                    if not controlled_powers:
                        logger.error(
                            f"BlocLLMAgent '{agent_identifier}' missing 'controlled_powers'. Skipping."
                        )
                        continue

                    agent = self.agent_factory.create_agent(
                        agent_id=agent_id_str,
                        country=agent_identifier,  # Not strictly used by BlocLLMAgent constructor signature's 'country'
                        config=current_agent_config,  # type="bloc_llm", model_id for bloc
                        game_id=self.game_config.game_id,
                        bloc_name=bloc_name,
                        controlled_powers=controlled_powers,
                    )
                else:
                    logger.warning(
                        f"Unsupported agent type '{agent_type}' for '{agent_identifier}'. Skipping."
                    )
                    continue

                if agent:
                    self._initialize_agent_state_ext(agent)
                    self.agents[agent_identifier] = (
                        agent  # Store by "FRANCE" or "ENTENTE_BLOC"
                    )
                    logger.info(
                        f"Agent for '{agent_identifier}' created and initialized: {agent.__class__.__name__}."
                    )

            except Exception as e:
                logger.error(
                    f"Failed to create or initialize agent for '{agent_identifier}' (type {agent_type}): {e}",
                    exc_info=True,
                )
                # Continue with other agents

        self.game_config.agents = (
            self.agents
        )  # Store the dict of created agents in GameConfig
        logger.info(
            f"All {len(self.agents)} agent entities initialized: {list(self.agents.keys())}"
        )

    def get_agent(self, agent_identifier: str) -> Optional[BaseAgent]:
        """
        Retrieves an initialized agent by its identifier (power name or bloc name).

        Args:
            agent_identifier: The identifier of the agent (e.g., "FRANCE" or "ENTENTE_BLOC").

        Returns:
            The BaseAgent instance, or None if not found.
        """
        return self.agents.get(agent_identifier)
