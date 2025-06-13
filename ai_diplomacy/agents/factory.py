"""
Agent factory for creating different types of agents based on configuration.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Protocol

from ai_diplomacy.agents.base import BaseAgent
from ai_diplomacy.agents.bloc_llm_agent import BlocLLMAgent
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.agents.neutral_agent import NeutralAgent
from ai_diplomacy.agents.scripted_agent import ScriptedAgent

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)

__all__ = ["AgentFactory"]


class AgentConfig(Protocol):
    """Defines the structure for agent configuration objects."""

    type: str
    personality: str


class AgentFactory:
    """
    Factory for creating different types of agents based on configuration.
    """

    def __init__(self):
        """Initialize the agent factory."""
        logger.info("AgentFactory initialized")

    def create_agent(
        self,
        agent_id: str,
        country: str,
        config: AgentConfig,
        *,
        bloc_name: str | None = None,
        controlled_powers: List[str] | None = None,
    ) -> BaseAgent:
        """
        Create an agent based on the provided configuration.
        """
        logger.info(
            f"Attempting to create agent of type '{config.type}' for "
            f"'{country if config.type != 'bloc_llm' else bloc_name}' with ID {agent_id}"
        )

        if config.type == "llm":
            return self._create_llm_agent(agent_id, country)
        if config.type == "scripted":
            return self._create_scripted_agent(agent_id, country, config)
        if config.type in ("neutral", "null"):
            return self._create_neutral_agent(agent_id, country)
        if config.type == "bloc_llm":
            if not bloc_name or not controlled_powers:
                raise ValueError("BlocLLMAgent requires a bloc_name and controlled_powers.")
            return self._create_bloc_llm_agent(agent_id, bloc_name, controlled_powers)

        raise ValueError(f"Unsupported agent type: {config.type}")

    def _create_llm_agent(self, agent_id: str, country: str) -> LLMAgent:
        """Create an LLM-based agent."""
        logger.debug(f"Creating LLMAgent for {country}")
        return LLMAgent(agent_id=agent_id, country=country)

    def _create_scripted_agent(self, agent_id: str, country: str, config: AgentConfig) -> ScriptedAgent:
        """Create a scripted agent."""
        personality = getattr(config, "personality", "neutral_hold")
        logger.debug(f"Creating ScriptedAgent for {country} with personality '{personality}'")
        return ScriptedAgent(agent_id=agent_id, country=country, personality=personality)

    def _create_neutral_agent(self, agent_id: str, country: str) -> NeutralAgent:
        """Create a NeutralAgent."""
        logger.debug(f"Creating NeutralAgent for {country}")
        return NeutralAgent(agent_id=agent_id, country=country)

    def _create_bloc_llm_agent(
        self,
        agent_id: str,
        bloc_name: str,
        controlled_powers: List[str],
    ) -> BlocLLMAgent:
        """Create a BlocLLMAgent."""
        logger.debug(f"Creating BlocLLMAgent for bloc '{bloc_name}' controlling {controlled_powers}")
        return BlocLLMAgent(
            agent_id=agent_id,
            bloc_name=bloc_name,
            controlled_powers=controlled_powers,
        )
