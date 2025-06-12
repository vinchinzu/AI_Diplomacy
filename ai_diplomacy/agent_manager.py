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
    from .agents.base import BaseAgent  # noqa

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
        self.agents: Dict[str, BaseAgent] = {}  # Keyed by agent identifier (power name or bloc name)
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
        logger.debug(f"Performing extended state initialization for {agent.agent_id} (currently minimal).")
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
        logger.info(f"Initializing agents based on configurations: {list(agent_configurations.keys())}")
        self.agents = {}  # Clear any previous agents

        for agent_identifier, config_details in agent_configurations.items():
            agent_type = config_details.get("type")
            model_id = config_details.get("model_id")  # Can be None for neutral

            # verbose_llm_debug should come from game_config
            verbose_llm_debug = getattr(self.game_config.args, "verbose_llm_debug", False)

            # Adapt the incoming config_details dict to match AgentConfig model
            if "country" in config_details:
                config_details["name"] = config_details.pop("country")

            # Ensure essential fields are present before unpacking
            config_details.setdefault("name", agent_identifier)
            config_details.setdefault("type", agent_type)
            config_details.setdefault("model_id", model_id)
            config_details.setdefault("verbose_llm_debug", verbose_llm_debug)

            current_agent_config = AgentConfig(**config_details)

            agent_id_str = f"{agent_identifier.lower().replace(' ', '_')}_{self.game_config.game_id}"

            logger.info(
                f"Creating agent for '{agent_identifier}' of type '{agent_type}' with model '{model_id if model_id else 'N/A'}'"
            )

            try:
                agent: Optional[BaseAgent] = None
                # Refactored agent creation to be more streamlined
                country_for_agent = agent_identifier  # The country/power name for single agents

                if agent_type in ("llm", "neutral", "scripted"):
                    agent = self.agent_factory.create_agent(
                        agent_id=agent_id_str,
                        country=country_for_agent,
                        config=current_agent_config,
                        game_config=self.game_config,
                        game_id=self.game_config.game_id,
                    )
                elif agent_type == "null":
                    # NullAgent is not created via factory, but directly
                    from .agents.null_agent import (
                        NullAgent,
                    )  # Ensure NullAgent is imported

                    agent = NullAgent(
                        agent_id=agent_id_str,  # agent_identifier could be "ITALY_NULL" or similar
                        power_name=country_for_agent,  # The actual power like "ITALY"
                    )
                    logger.info(f"Directly instantiating NullAgent for power: {country_for_agent}")
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
                        country=country_for_agent,  # Not strictly used by BlocLLMAgent constructor signature's 'country'
                        config=current_agent_config,  # type="bloc_llm", model_id for bloc
                        game_config=self.game_config,
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
                    self.agents[agent_identifier] = agent  # Store by "FRANCE" or "ENTENTE_BLOC"
                    logger.info(
                        f"Agent for '{agent_identifier}' created and initialized: {agent.__class__.__name__}."
                    )

            except Exception as e:
                logger.error(
                    f"Failed to create or initialize agent for '{agent_identifier}' (type {agent_type}): {e}",
                    exc_info=True,
                )
                # Continue with other agents

        self.game_config.agents = self.agents  # Store the dict of created agents in GameConfig
        logger.info(f"All {len(self.agents)} agent entities initialized: {list(self.agents.keys())}")

    def get_agent(self, agent_identifier: str) -> Optional[BaseAgent]:
        """
        Retrieves an initialized agent by its identifier (power name or bloc name).

        Args:
            agent_identifier: The identifier of the agent (e.g., "FRANCE" or "ENTENTE_BLOC").

        Returns:
            The BaseAgent instance, or None if not found.
        """
        return self.agents.get(agent_identifier)

    def get_agent_by_power(self, power_name: str) -> Optional[BaseAgent]:
        """
        Retrieves the agent responsible for a given power.

        This method maps a power (e.g., "FRANCE") to its controlling agent
        identifier (e.g., "ENTENTE_POWERS") and returns the corresponding agent instance.

        Args:
            power_name: The name of the power.

        Returns:
            The BaseAgent instance for that power, or None if not found.
        """
        agent_identifier = self.game_config.power_to_agent_id_map.get(power_name)
        if agent_identifier:
            return self.get_agent(agent_identifier)
        logger.warning(f"Could not find agent identifier for power '{power_name}' in power_to_agent_id_map.")
        return None
