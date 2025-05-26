"""
AI Diplomacy - Automated Diplomacy Game Playing with LLMs

This package provides a framework for playing Diplomacy using Large Language Models,
with support for multiple agent types, context providers, and usage tracking.
"""

# Expose the new agent classes for backward compatibility
from ai_diplomacy.agents.llm_agent import LLMAgent as DiplomacyAgent
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.base import BaseAgent
from ai_diplomacy.core.state import PhaseState
from ai_diplomacy.services.llm_coordinator import LLMCoordinator
from ai_diplomacy.services.config import AgentConfig, DiplomacyConfig

__all__ = [
    'DiplomacyAgent',  # Backward compatibility alias for LLMAgent
    'LLMAgent',        # Direct access to new LLMAgent
    'AgentFactory',
    'BaseAgent', 
    'PhaseState',
    'LLMCoordinator',
    'AgentConfig',
    'DiplomacyConfig'
]

# Re-export LLMAgent under its own name as well
from ai_diplomacy.agents.llm_agent import LLMAgent

__version__ = "2.0.0"  # Updated for the new architecture
