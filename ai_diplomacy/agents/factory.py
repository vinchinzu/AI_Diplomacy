"""
Agent factory for creating different types of agents based on configuration.
"""

import logging
from typing import Dict, Optional

from .base import BaseAgent
from .llm_agent import LLMAgent
from .scripted_agent import ScriptedAgent
from ..services.config import AgentConfig, DiplomacyConfig
from ..services.llm_coordinator import LLMCoordinator
from ..services.context_provider import ContextProviderFactory
from ..llm_utils import load_prompt_file

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Factory for creating different types of agents based on configuration.

    Supports both LLM and scripted agents, with clean separation between
    agent creation and game engine logic.
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
        country: str,
        config: AgentConfig,
        game_id: str = "unknown_game",
    ) -> BaseAgent:
        """
        Create an agent based on the provided configuration.

        Args:
            agent_id: Unique identifier for the agent
            country: Country/power the agent represents
            config: Agent configuration
            game_id: Game identifier for tracking

        Returns:
            A BaseAgent instance

        Raises:
            ValueError: If agent type is not supported
        """
        logger.info(f"Creating {config.type} agent for {country} with ID {agent_id}")

        if config.type == "llm":
            return self._create_llm_agent(agent_id, country, config, game_id)
        elif config.type == "scripted":
            return self._create_scripted_agent(agent_id, country, config)
        else:
            raise ValueError(f"Unsupported agent type: {config.type}")

    def _create_llm_agent(
        self, agent_id: str, country: str, config: AgentConfig, game_id: str
    ) -> LLMAgent:
        """Create an LLM-based agent."""
        if not config.model_id:
            raise ValueError(f"LLM agent for {country} requires model_id in config")

        return LLMAgent(
            agent_id=agent_id,
            country=country,
            config=config,
            game_id=game_id,
            llm_coordinator=self.llm_coordinator,
            context_provider_factory=self.context_provider_factory,
            prompt_loader=load_prompt_file,
        )

    def _create_scripted_agent(
        self, agent_id: str, country: str, config: AgentConfig
    ) -> ScriptedAgent:
        """Create a scripted agent."""
        # Use personality from config if available, otherwise default to neutral
        personality = getattr(config, "personality", "neutral")

        return ScriptedAgent(
            agent_id=agent_id, country=country, personality=personality
        )

    def create_agents_from_config(
        self, diplomacy_config: DiplomacyConfig, game_id: str = "unknown_game"
    ) -> Dict[str, BaseAgent]:
        """
        Create all agents defined in a DiplomacyConfig.

        Args:
            diplomacy_config: Complete diplomacy configuration
            game_id: Game identifier for tracking

        Returns:
            Dictionary mapping country names to agent instances
        """
        agents = {}

        for agent_config in diplomacy_config.agents:
            try:
                agent_id = f"{agent_config.country.lower()}_{game_id}"
                agent = self.create_agent(
                    agent_id=agent_id,
                    country=agent_config.country,
                    config=agent_config,
                    game_id=game_id,
                )
                agents[agent_config.country] = agent
                logger.info(f"Created agent for {agent_config.country}")

            except Exception as e:
                logger.error(
                    f"Failed to create agent for {agent_config.country}: {e}",
                    exc_info=True,
                )
                # Continue creating other agents

        logger.info(f"Created {len(agents)} agents from configuration")
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
            # Check required fields
            if not config.country or not config.type:
                logger.error(
                    f"Agent config missing required fields: country={config.country}, type={config.type}"
                )
                return False

            # Validate agent type
            if config.type not in ["llm", "scripted"]:
                logger.error(f"Invalid agent type: {config.type}")
                return False

            # LLM agents need model_id
            if config.type == "llm" and not config.model_id:
                logger.error(f"LLM agent for {config.country} missing model_id")
                return False

            # Validate country name
            if config.country not in [
                "AUSTRIA",
                "ENGLAND",
                "FRANCE",
                "GERMANY",
                "ITALY",
                "RUSSIA",
                "TURKEY",
            ]:
                logger.error(f"Invalid country: {config.country}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating agent config: {e}", exc_info=True)
            return False
