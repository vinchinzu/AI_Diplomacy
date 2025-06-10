"""
AI Diplomacy - Automated Diplomacy Game Playing with LLMs

This package provides a framework for playing Diplomacy using Large Language Models,
with support for multiple agent types, context providers, and usage tracking.
"""

# Expose the new agent classes for backward compatibility
# Attempt to resolve circular import by importing llm_utils first
from . import llm_utils  # Make llm_utils available in the package namespace

from ai_diplomacy.agents.llm_agent import LLMAgent as DiplomacyAgent
from ai_diplomacy.agents.llm_agent import (
    LLMAgent,
)  # Keep this for direct access if needed by __all__
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.base import BaseAgent
from ai_diplomacy.core.state import PhaseState
from generic_llm_framework.llm_coordinator import LLMCoordinator # Updated import
from ai_diplomacy.services.config import AgentConfig, DiplomacyConfig


__all__ = [
    "DiplomacyAgent",  # Backward compatibility alias for LLMAgent
    "LLMAgent",
    "AgentFactory",
    "BaseAgent",
    "PhaseState",
    "LLMCoordinator",
    "AgentConfig",
    "DiplomacyConfig",
    "llm_utils",  # Expose llm_utils if it's intended to be public
]

__version__ = "2.0.0"  # Updated for the new architecture
