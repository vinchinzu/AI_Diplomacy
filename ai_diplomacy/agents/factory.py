"""
Agent factory for creating different types of agents based on configuration.
"""

import logging
from typing import Dict, Optional, List  # Added List

from .base import BaseAgent
from .llm_agent import LLMAgent
from .scripted_agent import ScriptedAgent
from .neutral_agent import NeutralAgent  # Import NeutralAgent
from .bloc_llm_agent import BlocLLMAgent  # Import BlocLLMAgent
from ..services.config import (
    AgentConfig,
    DiplomacyConfig,
)  # DiplomacyConfig might not be used here directly anymore
from ..services.llm_coordinator import LLMCoordinator
from ..services.context_provider import ContextProviderFactory
from ..llm_utils import load_prompt_file

logger = logging.getLogger(__name__)

__all__ = ["AgentFactory"]


class AgentFactory:
    """
    Factory for creating different types of agents based on configuration.

    Supports LLM, scripted, neutral, and bloc LLM agents.
    """

    def __init__(
        self,
        llm_coordinator: Optional[LLMCoordinator] = None,
        context_provider_factory: Optional[ContextProviderFactory] = None,
    ):
        """
        Initialize the agent factory.

        Args:
            llm_coordinator: Shared LLM coordinator instance (will create if None)
            context_provider_factory: Shared context provider factory (will create if None)
        """
        self.llm_coordinator = llm_coordinator or LLMCoordinator()
        self.context_provider_factory = (
            context_provider_factory or ContextProviderFactory()
        )
        logger.info("AgentFactory initialized")

    def create_agent(
        self,
        agent_id: str,
        country: str,  # For NeutralAgent and LLMAgent (single country)
        config: AgentConfig,
        game_id: str = "unknown_game",
        # New optional parameters for BlocLLMAgent
        bloc_name: Optional[str] = None,
        controlled_powers: Optional[List[str]] = None,
    ) -> BaseAgent:
        """
        Create an agent based on the provided configuration.

        Args:
            agent_id: Unique identifier for the agent
            country: Country/power the agent represents (for single-power agents)
            config: Agent configuration (contains agent_type, model_id, etc.)
            game_id: Game identifier for tracking
            bloc_name: Name of the bloc, if creating a BlocLLMAgent (e.g., "ENTENTE_BLOC")
            controlled_powers: List of powers controlled by the bloc, if creating a BlocLLMAgent

        Returns:
            A BaseAgent instance

        Raises:
            ValueError: If agent type is not supported or required parameters are missing
        """
        logger.info(
            f"Attempting to create agent of type '{config.type}' for '{country if config.type != 'bloc_llm' else bloc_name}' with ID {agent_id}"
        )

        if config.type == "llm":
            return self._create_llm_agent(agent_id, country, config, game_id)
        elif config.type == "scripted":
            return self._create_scripted_agent(agent_id, country, config)
        elif config.type == "neutral":  # New condition for NeutralAgent
            return self._create_neutral_agent(agent_id, country, config)
        elif config.type == "null": # "null" type will use NeutralAgent's creation logic
            return self._create_neutral_agent(agent_id, country, config)
        elif config.type == "bloc_llm":  # New condition for BlocLLMAgent
            if not bloc_name or not controlled_powers:
                raise ValueError(
                    "BlocLLMAgent requires bloc_name and controlled_powers."
                )
            # The 'country' argument to create_agent is not directly used by BlocLLMAgent's constructor,
            # as it takes controlled_powers. We pass it along for consistency but it's overshadowed.
            return self._create_bloc_llm_agent(
                agent_id, bloc_name, controlled_powers, config, game_id
            )
        else:
            raise ValueError(f"Unsupported agent type: {config.type}")

    def _create_llm_agent(
        self, agent_id: str, country: str, config: AgentConfig, game_id: str
    ) -> LLMAgent:
        """Create an LLM-based agent."""
        if not config.model_id:
            raise ValueError(f"LLM agent for {country} requires model_id in config")
        logger.debug(f"Creating LLMAgent for {country} with model {config.model_id}")
        return LLMAgent(
            agent_id=agent_id,
            country=country,
            config=config,
            game_id=game_id,
            llm_coordinator=self.llm_coordinator,
            context_provider_factory=self.context_provider_factory,
            prompt_loader=load_prompt_file,  # Assuming default prompt loader
        )

    def _create_scripted_agent(
        self, agent_id: str, country: str, config: AgentConfig
    ) -> ScriptedAgent:
        """Create a scripted agent."""
        personality = getattr(
            config, "personality", "neutral_hold"
        )  # Default to neutral_hold
        logger.debug(
            f"Creating ScriptedAgent for {country} with personality '{personality}'"
        )
        return ScriptedAgent(
            agent_id=agent_id, country=country, personality=personality
        )

    def _create_neutral_agent(
        self,
        agent_id: str,
        country: str,
        config: AgentConfig,  # Config might be minimal for Neutral
    ) -> NeutralAgent:
        """Create a NeutralAgent."""
        logger.debug(f"Creating NeutralAgent for {country}")
        # NeutralAgent doesn't need much from AgentConfig beyond type, but pass it for consistency.
        return NeutralAgent(
            agent_id=agent_id,
            country=country,
            # config is not directly used by NeutralAgent constructor other than for consistency
        )

    def _create_bloc_llm_agent(
        self,
        agent_id: str,
        bloc_name: str,
        controlled_powers: List[str],
        config: AgentConfig,  # Config for the LLM model of the bloc
        game_id: str,
    ) -> BlocLLMAgent:
        """Create a BlocLLMAgent."""
        if not config.model_id:
            raise ValueError(
                f"BlocLLMAgent for {bloc_name} requires model_id in config"
            )
        if not controlled_powers:
            raise ValueError(
                f"BlocLLMAgent for {bloc_name} requires a list of controlled_powers."
            )

        logger.debug(
            f"Creating BlocLLMAgent for bloc '{bloc_name}' controlling {controlled_powers} with model {config.model_id}"
        )
        return BlocLLMAgent(
            agent_id=agent_id,  # e.g., "entente_bloc_game123"
            bloc_name=bloc_name,
            controlled_powers=controlled_powers,
            config=config,  # Contains model_id, temperature, etc.
            game_id=game_id,
            llm_coordinator=self.llm_coordinator,
            context_provider_factory=self.context_provider_factory,
            prompt_loader=load_prompt_file,  # Assuming default prompt loader
        )

    # create_agents_from_config might need adjustment if DiplomacyConfig structure changes
    # or if it needs to pass bloc_name and controlled_powers.
    # For now, this method is less critical as AgentManager directly calls create_agent.
    # We will assume AgentManager will be updated to provide these new parameters.

    def create_agents_from_config(
        self, diplomacy_config: DiplomacyConfig, game_id: str = "unknown_game"
    ) -> Dict[str, BaseAgent]:
        """
        Create all agents defined in a DiplomacyConfig.
        NOTE: This method might need significant updates if DiplomacyConfig
        is the source for bloc definitions. Currently, AgentManager is expected
        to handle the logic of identifying blocs and calling create_agent appropriately.
        """
        agents = {}
        logger.warning(
            "create_agents_from_config may need updates for bloc agent creation logic if used directly with complex configs."
        )

        for (
            agent_config
        ) in diplomacy_config.agents:  # agent_config is of type AgentConfig
            try:
                # This loop assumes one AgentConfig per agent.
                # For BlocLLMAgent, the AgentConfig would be for the bloc itself.
                # The mapping of this config to a bloc_name and controlled_powers
                # would need to be handled by the caller or be part of AgentConfig extension.

                agent_id_country_part = (
                    agent_config.country
                )  # Fallback for single powers

                # This is a placeholder: how do we get bloc_name and controlled_powers from agent_config?
                # This method is likely superseded by AgentManager's direct calls to create_agent.
                # If agent_config.type == "bloc_llm", we'd need more info from agent_config.
                # For now, assume this method is primarily for non-bloc agents if called directly.
                if agent_config.type == "bloc_llm":
                    logger.error(
                        f"create_agents_from_config cannot create bloc_llm for {agent_config.country} without bloc_name and controlled_powers. Skipping."
                    )
                    continue

                agent = self.create_agent(
                    agent_id=f"{agent_id_country_part.lower()}_{game_id}",
                    country=agent_config.country,  # Used for single agents
                    config=agent_config,
                    game_id=game_id,
                    # bloc_name and controlled_powers would be None here, problematic for bloc_llm
                )
                agents[agent_config.country] = (
                    agent  # Keying by country might be an issue for blocs
                )
                logger.info(
                    f"Created agent for {agent_config.country} via create_agents_from_config"
                )

            except Exception as e:
                logger.error(
                    f"Failed to create agent for {agent_config.country} via create_agents_from_config: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Created {len(agents)} agents from configuration via create_agents_from_config"
        )
        return agents

    def validate_agent_config(self, config: AgentConfig) -> bool:
        """
        Validate that an agent configuration is valid.
        Args:
            config: Agent configuration to validate
        Returns:
            True if valid, False otherwise
        """
        try:
            if (
                not config.country and config.type != "bloc_llm"
            ):  # country is not primary for bloc, bloc_name is
                logger.error(
                    "Agent config missing required field: country (for non-bloc types)"
                )
                return False
            if not config.type:
                logger.error("Agent config missing required field: type")
                return False

            if config.type not in [
                "llm",
                "scripted",
                "neutral",
                "bloc_llm",
                "null", # Added "null" as a valid type
            ]:  # Added new types
                logger.error(f"Invalid agent type: {config.type}")
                return False

            if config.type == "llm" and not config.model_id:
                logger.error(f"LLM agent for {config.country} missing model_id")
                return False

            if config.type == "bloc_llm" and not config.model_id:
                # Assuming bloc_name is part of config or handled by caller for logging
                logger.error("BlocLLMAgent missing model_id in config")
                return False

            # Country validation might not apply if config.country is a bloc name
            # For single agents, country should be one of the standard powers.
            if config.type in ["llm", "scripted", "neutral"]:
                if config.country not in [
                    "AUSTRIA",
                    "ENGLAND",
                    "FRANCE",
                    "GERMANY",
                    "ITALY",
                    "RUSSIA",
                    "TURKEY",
                    # Allow potential bloc names if they are passed in 'country' field for some reason,
                    # but primarily, validation of controlled_powers for a bloc is separate.
                    # This validation is primarily for single-power agent configs.
                ]:
                    # Temporarily relax this for wwi_two_player scenario where country might be "ENTENTE_BLOC"
                    # This part of validation might need rethinking based on how AgentConfig is used for blocs.
                    # logger.warning(f"Country '{config.country}' not a standard power. Ensure this is intended (e.g., a bloc name).")
                    pass

            return True

        except Exception as e:
            logger.error(f"Error validating agent config: {e}", exc_info=True)
            return False
