"""
Pluggable context provider system for agents.
Supports both inline context (embedded JSON) and MCP-based context (using tools).
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ..core.state import PhaseState
from .config import AgentConfig
from .. import constants  # Import constants

logger = logging.getLogger(__name__)

__all__ = [
    "ContextData",
    "ContextProvider",
    "InlineContextProvider",
    "MCPContextProvider",
    "ContextProviderFactory",
]


@dataclass
class ContextData:
    """Container for all context information needed by agents."""

    phase_state: PhaseState
    possible_orders: Dict[str, List[str]]
    game_history: Optional[Any] = None  # GameHistory object
    recent_messages: Optional[str] = None
    strategic_analysis: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


class ContextProvider(ABC):
    """
    Abstract base class for context providers.

    Context providers are responsible for delivering game state and context
    information to agents in different formats (inline vs MCP tools).
    """

    @abstractmethod
    async def provide_context(
        self,
        agent_id: str,
        country: str,
        context_data: ContextData,
        agent_config: AgentConfig,
    ) -> Dict[str, Any]:
        """
        Provide context information to an agent.

        Args:
            agent_id: Unique identifier for the requesting agent
            country: The country/power the agent represents
            context_data: All available context information
            agent_config: Agent configuration

        Returns:
            Dictionary containing context in provider-specific format
        """
        pass

    @abstractmethod
    def get_provider_type(self) -> str:
        """Return the type identifier for this provider."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available/configured correctly."""
        pass


class InlineContextProvider(ContextProvider):
    """
    Provides context by embedding all information directly in prompts.

    This is the traditional approach where all game state, possible orders,
    and strategic analysis are included as formatted text in the prompt.
    """

    def __init__(self):
        """Initialize the inline context provider."""
        self.provider_type = constants.CONTEXT_PROVIDER_INLINE
        logger.info("InlineContextProvider initialized")

    async def provide_context(
        self,
        agent_id: str,
        country: str,
        context_data: ContextData,
        agent_config: AgentConfig,
    ) -> Dict[str, Any]:
        """
        Provide inline context by formatting all data as text.

        Returns:
            Dictionary with 'context_text' containing formatted context
        """
        logger.debug(f"Providing inline context for {country}")

        try:
            # Format phase state information
            phase_info = self._format_phase_state(context_data.phase_state, country)

            # Format possible orders
            orders_info = self._format_possible_orders(
                context_data.possible_orders, country
            )

            # Format strategic analysis if available
            strategic_info = self._format_strategic_analysis(
                context_data.strategic_analysis
            )

            # Format recent messages
            messages_info = self._format_recent_messages(context_data.recent_messages)

            # Combine all context sections
            context_sections = [
                constants.CONTEXT_SECTION_HEADER_GAME_STATE,
                phase_info,
                "",
                constants.CONTEXT_SECTION_HEADER_POSSIBLE_ORDERS,
                orders_info,
                "",
                constants.CONTEXT_SECTION_HEADER_STRATEGIC_ANALYSIS,
                strategic_info,
                "",
                constants.CONTEXT_SECTION_HEADER_RECENT_MESSAGES,
                messages_info,
            ]

            context_text = "\n".join(context_sections)

            return {
                "provider_type": constants.CONTEXT_PROVIDER_INLINE,
                "context_text": context_text,
                "tools_available": False,
            }

        except Exception as e:
            logger.error(
                f"Error providing inline context for {country}: {e}", exc_info=True
            )
            # Return minimal fallback context
            return {
                "provider_type": constants.CONTEXT_PROVIDER_INLINE,
                "context_text": f"Context generation failed: {e}",
                "tools_available": False,
            }

    def _format_phase_state(self, phase_state: PhaseState, country: str) -> str:
        """Format phase state information as text."""
        lines = [
            f"Phase: {phase_state.phase_name}",
            f"Year: {phase_state.year}, Season: {phase_state.season}",
            f"Phase Type: {phase_state.phase_type}",
            "",
            f"Your Units ({country}):",
        ]

        my_units = phase_state.get_power_units(country)
        if my_units:
            for unit in my_units:
                lines.append(f"  - {unit}")
        else:
            lines.append("  - No units")

        lines.append("")
        lines.append(f"Your Supply Centers ({country}):")
        my_centers = phase_state.get_power_centers(country)
        if my_centers:
            for center in my_centers:
                lines.append(f"  - {center}")
        else:
            lines.append("  - No supply centers")

        lines.append("")
        lines.append("All Powers Status:")
        for power in sorted(phase_state.powers):
            if phase_state.is_power_eliminated(power):
                status = constants.STATUS_ELIMINATED_PLAYER
            else:
                center_count = phase_state.get_center_count(power)
                unit_count = len(phase_state.get_power_units(power))
                status = f"({center_count} centers, {unit_count} units)"
            lines.append(f"  - {power}: {status}")

        return "\n".join(lines)

    def _format_possible_orders(
        self, possible_orders: Dict[str, List[str]], country: str
    ) -> str:
        """Format possible orders as text."""
        if not possible_orders:
            return "No orders available for this phase."

        lines = []
        for location, orders in possible_orders.items():
            lines.append(f"Unit at {location}:")
            for order in orders:
                lines.append(f"  - {order}")
            lines.append("")

        return "\n".join(lines)

    def _format_strategic_analysis(self, strategic_analysis: Optional[str]) -> str:
        """Format strategic analysis as text."""
        if not strategic_analysis:
            return "No strategic analysis available."
        return strategic_analysis

    def _format_recent_messages(self, recent_messages: Optional[str]) -> str:
        """Format recent messages as text."""
        if not recent_messages:
            return "No recent messages."
        return recent_messages

    def get_provider_type(self) -> str:
        """Return the provider type."""
        return self.provider_type

    def is_available(self) -> bool:
        """Inline context is always available."""
        return True


class MCPContextProvider(ContextProvider):
    """
    Provides context through MCP (Model Context Protocol) tools.

    This provider exposes game state and analysis as callable tools
    that MCP-aware models can invoke dynamically during reasoning.
    """

    def __init__(self, mcp_client=None):
        """
        Initialize the MCP context provider.

        Args:
            mcp_client: MCP client instance (will create if None)
        """
        self.provider_type = constants.CONTEXT_PROVIDER_MCP
        self.mcp_client = mcp_client
        logger.info(f"MCP client set for {self.__class__.__name__}")

    async def provide_context(
        self,
        agent_id: str,
        country: str,
        context_data: ContextData,
        agent_config: AgentConfig,
    ) -> Dict[str, Any]:
        """
        Provide MCP-based context through tool definitions.

        Returns:
            Dictionary with tool definitions and minimal prompt context
        """
        logger.debug(f"Providing MCP context for {country}")

        if not self.is_available():
            logger.warning(
                f"MCP provider not available for {country}, falling back to basic context"
            )
            return {
                "provider_type": constants.CONTEXT_PROVIDER_MCP,
                "context_text": "MCP tools not available - using basic context",
                "tools_available": False,
                "tools": [],
            }

        try:
            # Define available tools for this agent
            tools = self._define_available_tools(agent_id, country, context_data)

            # Provide minimal prompt context (MCP tools will provide the rest)
            basic_context = f"""
You are playing as {country} in Diplomacy.
Current Phase: {context_data.phase_state.phase_name}

You have access to the following tools to get detailed information:
{self._format_tool_descriptions(tools)}

Use these tools to gather the information you need to make decisions.
            """.strip()

            return {
                "provider_type": constants.CONTEXT_PROVIDER_MCP,
                "context_text": basic_context,
                "tools_available": True,
                "tools": tools,
            }

        except Exception as e:
            logger.error(
                f"Error providing MCP context for {country}: {e}", exc_info=True
            )
            return {
                "provider_type": constants.CONTEXT_PROVIDER_MCP,
                "context_text": f"MCP context failed: {e}",
                "tools_available": False,
                "tools": [],
            }

    def _define_available_tools(
        self, agent_id: str, country: str, context_data: ContextData
    ) -> List[Dict[str, Any]]:
        """Define MCP tools available to this agent."""
        tools = [
            {
                "name": constants.MCP_TOOL_BOARD_STATE,
                "description": f"Get current board state for {country} including units, centers, and power status",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_details": {
                            "type": "boolean",
                            "description": "Include detailed analysis",
                            "default": True,
                        }
                    },
                },
            },
            {
                "name": constants.MCP_TOOL_POSSIBLE_ORDERS,
                "description": f"Get all possible orders for {country}'s units this phase",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_strategic_analysis": {
                            "type": "boolean",
                            "description": "Include strategic analysis of each order",
                            "default": False,
                        }
                    },
                },
            },
            {
                "name": constants.MCP_TOOL_RECENT_MESSAGES,
                "description": "Get recent diplomatic messages involving this power",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phases_back": {
                            "type": "integer",
                            "description": "How many phases back to look",
                            "default": 3,
                        }
                    },
                },
            },
        ]

        return tools

    def _format_tool_descriptions(self, tools: List[Dict[str, Any]]) -> str:
        """Format tool descriptions for the prompt."""
        descriptions = []
        for tool in tools:
            descriptions.append(f"- {tool['name']}: {tool['description']}")
        return "\n".join(descriptions)

    def get_provider_type(self) -> str:
        """Return the provider type."""
        return self.provider_type

    def is_available(self) -> bool:
        """Check if MCP client is configured and available."""
        return self.mcp_client is not None


class ContextProviderFactory:
    """
    Factory for creating and managing context providers.

    Handles automatic provider selection based on model capabilities
    and configuration preferences.
    """

    def __init__(self):
        """Initialize the factory."""
        self._providers = {}
        self._register_default_providers()
        logger.info("ContextProviderFactory initialized")

    def _register_default_providers(self):
        """Register the default context providers."""
        self._providers[constants.CONTEXT_PROVIDER_INLINE] = InlineContextProvider()
        self._providers[constants.CONTEXT_PROVIDER_MCP] = MCPContextProvider()

    def get_provider(self, provider_type: str) -> ContextProvider:
        """
        Get a context provider by type.

        Args:
            provider_type: Type of provider ("inline", "mcp", or "auto")

        Returns:
            ContextProvider instance

        Raises:
            ValueError: If provider type is not supported
        """
        if provider_type == constants.CONTEXT_PROVIDER_AUTO:
            # Auto-selection logic - prefer MCP if available, fallback to inline
            if self._providers[constants.CONTEXT_PROVIDER_MCP].is_available():
                return self._providers[constants.CONTEXT_PROVIDER_MCP]
            else:
                return self._providers[constants.CONTEXT_PROVIDER_INLINE]

        if provider_type not in self._providers:
            raise ValueError(f"Unknown context provider type: {provider_type}")

        provider = self._providers[provider_type]

        if not provider.is_available():
            logger.warning(
                f"Requested provider '{provider_type}' is not available, falling back to inline"
            )
            return self._providers[constants.CONTEXT_PROVIDER_INLINE]

        return provider

    def get_available_providers(self) -> List[str]:
        """Get list of available provider types."""
        return [
            ptype
            for ptype, provider in self._providers.items()
            if provider.is_available()
        ]
