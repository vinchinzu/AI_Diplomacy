"""
Functions for managing the lifecycle of Diplomacy agents during runtime,
including their creation, initialization, and retrieval.
"""

import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional

from ..agents.base import BaseAgent
from ..agents.factory import AgentFactory
from ..game_config import GameConfig

logger = logging.getLogger(__name__)


def initialize_agents(
    game_config: "GameConfig",
    agent_configurations: Dict[str, Dict[str, Any]],
):
    """
    Creates and initializes agent instances based on provided configurations.

    Args:
        game_config: The game configuration object, which will be populated with agents.
        agent_configurations: A dictionary where keys are agent identifiers
            (e.g., "FRANCE") and values are dictionaries containing agent setup details.
    """
    logger.info(f"Initializing agents based on configurations: {list(agent_configurations.keys())}")
    agents: Dict[str, BaseAgent] = {}
    agent_factory = AgentFactory()

    for agent_identifier, config_details in agent_configurations.items():
        agent_type = config_details.get("type")
        model_id = config_details.get("model_id")

        verbose_llm_debug = getattr(game_config.args, "verbose_llm_debug", False)

        if "country" in config_details:
            config_details["name"] = config_details.pop("country")

        config_details.setdefault("name", agent_identifier)
        config_details.setdefault("type", agent_type)
        config_details.setdefault("model_id", model_id)
        config_details.setdefault("verbose_llm_debug", verbose_llm_debug)

        current_agent_config = SimpleNamespace(**config_details)
        agent_id_str = f"{agent_identifier.lower().replace(' ', '_')}_{game_config.game_id}"

        logger.info(
            f"Creating agent for '{agent_identifier}' of type '{agent_type}' with model '{model_id if model_id else 'N/A'}'"
        )

        try:
            agent: Optional[BaseAgent] = None
            country_for_agent = agent_identifier

            if agent_type in ("llm", "neutral", "scripted"):
                agent = agent_factory.create_agent(
                    agent_id=agent_id_str,
                    country=country_for_agent,
                    config=current_agent_config,
                )
            elif agent_type == "null":
                from ..agents.null_agent import NullAgent

                agent = NullAgent(
                    agent_id=agent_id_str,
                    power_name=country_for_agent,
                )
            elif agent_type == "bloc_llm":
                bloc_name = config_details.get("bloc_name", agent_identifier)
                controlled_powers = config_details.get("controlled_powers")
                if not controlled_powers:
                    logger.error(f"BlocLLMAgent '{agent_identifier}' missing 'controlled_powers'. Skipping.")
                    continue

                agent = agent_factory.create_agent(
                    agent_id=agent_id_str,
                    country=country_for_agent,
                    config=current_agent_config,
                    bloc_name=bloc_name,
                    controlled_powers=controlled_powers,
                )
            else:
                logger.warning(f"Unsupported agent type '{agent_type}' for '{agent_identifier}'. Skipping.")
                continue

            if agent:
                agents[agent_identifier] = agent
                logger.info(f"Agent for '{agent_identifier}' created and initialized: {agent.__class__.__name__}.")

        except Exception as e:
            logger.error(
                f"Failed to create or initialize agent for '{agent_identifier}' (type {agent_type}): {e}",
                exc_info=True,
            )
    game_config.agents = agents
    logger.info(f"All {len(agents)} agent entities initialized: {list(agents.keys())}")


def get_agent(game_config: "GameConfig", agent_identifier: str) -> Optional[BaseAgent]:
    """
    Retrieves an initialized agent by its identifier.

    Args:
        game_config: The game configuration containing the initialized agents.
        agent_identifier: The identifier of the agent (e.g., "FRANCE").

    Returns:
        The BaseAgent instance, or None if not found.
    """
    return game_config.agents.get(agent_identifier)


def get_agent_by_power(game_config: "GameConfig", power_name: str) -> Optional[BaseAgent]:
    """
    Retrieves the agent responsible for a given power.

    Args:
        game_config: The game configuration containing agent and power mappings.
        power_name: The name of the power.

    Returns:
        The BaseAgent instance for that power, or None if not found.
    """
    agent_identifier = game_config.power_to_agent_id_map.get(power_name)
    if agent_identifier:
        return get_agent(game_config, agent_identifier)
    logger.warning(f"Could not find agent identifier for power '{power_name}' in power_to_agent_id_map.")
    return None 