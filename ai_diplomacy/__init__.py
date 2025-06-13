"""
AI Diplomacy - Automated Diplomacy Game Playing with LLMs

This package provides a framework for playing Diplomacy using Large Language Models,
with support for multiple agent types, context providers, and usage tracking.
"""

from ai_diplomacy.agents.llm_agent import LLMAgent as DiplomacyAgent
from ai_diplomacy.agents.llm_agent import (
    LLMAgent,
)  # Keep this for direct access if needed by __all__
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.base import BaseAgent
from ai_diplomacy.core.state import PhaseState


__all__ = [
    "DiplomacyAgent",  # Backward compatibility alias for LLMAgent
    "LLMAgent",
    "AgentFactory",
    "BaseAgent",
    "PhaseState",
]

__version__ = "2.0.0"
