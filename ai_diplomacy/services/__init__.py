"""
Subpackage for reusable infrastructure services in AI Diplomacy.

This package provides core services such as configuration management (loading and
validating game/agent settings), context provision to agents (inline or via MCP),
LLM call coordination (model pooling, usage tracking), and detailed usage analytics.
"""

from .config import (
    DiplomacyConfig,
    AgentConfig,
    GameConfig,
    resolve_context_provider,
    supports_tools,
)
from .context_provider import (
    ContextProvider,
    InlineContextProvider,
    MCPContextProvider,
    ContextProviderFactory,
    ContextData,
)
from .llm_coordinator import (
    LLMCoordinator,
    LLMCallResult,
    get_usage_stats_by_country,
    get_total_usage_stats,
)
from .usage_tracker import (
    UsageTracker,
    UsageStats,
    GameSummary,
)  # Added create_datasette_config

__all__ = [
    # From config.py
    "DiplomacyConfig",
    "AgentConfig",
    "GameConfig",
    "resolve_context_provider",
    "supports_tools",
    # From context_provider.py
    "ContextProvider",
    "InlineContextProvider",
    "MCPContextProvider",
    "ContextProviderFactory",
    "ContextData",
    # From llm_coordinator.py
    "LLMCoordinator",
    "LLMCallResult",
    "get_usage_stats_by_country",  # Re-exported from llm_coordinator for convenience/legacy
    "get_total_usage_stats",  # Re-exported from llm_coordinator for convenience/legacy
    # From usage_tracker.py
    "UsageTracker",
    "UsageStats",
    "GameSummary",
    # "create_datasette_config", # Decided not to export this as it's more of a utility script function
]
