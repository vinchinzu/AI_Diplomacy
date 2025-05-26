# ai_diplomacy/initialization.py
import logging
from typing import TYPE_CHECKING, Dict, Any, Tuple

if TYPE_CHECKING:
    from diplomacy import Game
    from diplomacy.models.game import GameHistory
    from .agents.base import BaseAgent

logger = logging.getLogger(__name__)


async def initialize_agent_state_ext(
    agent: 'BaseAgent', 
    game: 'Game', 
    game_history: 'GameHistory', 
    log_file_path: str
):
    """
    DEPRECATED: This function is being phased out in favor of the new agent system.
    
    The new BaseAgent interface handles initialization differently.
    This function now just logs a warning and returns.
    """
    power_name = agent.country
    logger.warning(f"initialize_agent_state_ext() is deprecated. Agent {power_name} initialization should be handled by the agent itself.")
    return  # Early return - this function is deprecated


async def initialize_agent_state_concurrently(
    agent: 'BaseAgent',
    game: 'Game',
    game_history: 'GameHistory',
    power_name: str,
    initial_prompt_template: str
) -> Tuple[str, bool, str, Dict[str, Any]]:
    """
    DEPRECATED: This function is being phased out in favor of the new agent system.
    
    Returns a failure status to indicate the function is deprecated.
    """
    logger.warning(f"initialize_agent_state_concurrently() is deprecated for {power_name}.")
    return power_name, False, "Deprecated", {}


async def initialize_agents_concurrently(
    agents: Dict[str, 'BaseAgent'],
    game: 'Game',
    game_history: 'GameHistory',
    initial_prompt_template_str: str
) -> None:
    """
    DEPRECATED: This function is being phased out in favor of the new agent system.
    
    The new agent system handles initialization through the agent factory and configuration.
    """
    logger.warning("initialize_agents_concurrently() is deprecated. Use the new agent factory system instead.")
    return
