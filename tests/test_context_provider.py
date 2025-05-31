import logging
import pytest
from unittest.mock import AsyncMock
from ai_diplomacy.core.state import PhaseState
from ai_diplomacy.services.config import AgentConfig
from ai_diplomacy.services.context_provider import (
    ContextProviderFactory,
    InlineContextProvider,
    MCPContextProvider,
    ContextData,
)

logger = logging.getLogger(__name__)

@pytest.mark.unit
def test_context_provider_factory():
    """Test the context provider factory."""
    logger.info("Testing ContextProviderFactory...")

    factory = ContextProviderFactory()

    # Test inline provider
    inline_provider = factory.get_provider("inline")
    assert isinstance(inline_provider, InlineContextProvider)
    assert inline_provider.is_available()

    # Test MCP provider (should fallback to inline since MCP client not configured)
    mcp_provider_fallback = factory.get_provider("mcp")
    assert isinstance(mcp_provider_fallback, InlineContextProvider)  # Should fallback

    # Test auto provider (should return inline since MCP not available)
    auto_provider = factory.get_provider("auto")
    assert isinstance(auto_provider, InlineContextProvider)

    # Test available providers
    available = factory.get_available_providers()
    assert "inline" in available

    logger.info("✓ ContextProviderFactory working correctly")

@pytest.mark.unit
@pytest.mark.asyncio
async def test_inline_context_provider():
    """Test the inline context provider."""
    logger.info("Testing InlineContextProvider...")

    provider = InlineContextProvider()

    # Create test phase state
    phase_state = PhaseState(
        phase_name="S1901M",
        year=1901,
        season="SPRING",
        phase_type="MOVEMENT",
        powers=frozenset(["FRANCE", "GERMANY"]),
        units={"FRANCE": ["A PAR", "F BRE"], "GERMANY": ["A BER", "F KIE"]},
        supply_centers={
            "FRANCE": ["PAR", "BRE", "MAR"],
            "GERMANY": ["BER", "KIE", "MUN"],
        },
    )

    # Create test context data
    context_data = ContextData(
        phase_state=phase_state,
        possible_orders={
            "A PAR": ["A PAR H", "A PAR-BUR"],
            "F BRE": ["F BRE H", "F BRE-ENG"],
        },
        recent_messages="France to Germany: Hello!",
        strategic_analysis="Paris is well defended.",
    )

    # Create test agent config
    agent_config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini")

    # Test context provision
    result = await provider.provide_context(
        "test-agent", "FRANCE", context_data, agent_config
    )

    assert result["provider_type"] == "inline"
    assert "context_text" in result
    assert result["tools_available"] is False

    # Check that context contains expected information
    context_text = result["context_text"]
    assert "FRANCE" in context_text
    assert "S1901M" in context_text
    assert "A PAR" in context_text
    assert "F BRE" in context_text
    assert "Hello!" in context_text

    logger.info("✓ InlineContextProvider working correctly")

@pytest.mark.unit
@pytest.mark.asyncio
async def test_mcp_context_provider():
    """Test the MCP context provider (should show tools are not available)."""
    logger.info("Testing MCPContextProvider...")

    provider = MCPContextProvider()

    # Create test data (same as inline test)
    phase_state = PhaseState(
        phase_name="S1901M",
        year=1901,
        season="SPRING",
        phase_type="MOVEMENT",
        powers=frozenset(["FRANCE", "GERMANY"]),
        units={"FRANCE": ["A PAR", "F BRE"], "GERMANY": ["A BER", "F KIE"]},
        supply_centers={
            "FRANCE": ["PAR", "BRE", "MAR"],
            "GERMANY": ["BER", "KIE", "MUN"],
        },
    )

    context_data = ContextData(
        phase_state=phase_state,
        possible_orders={"A PAR": ["A PAR H", "A PAR-BUR"]},
        recent_messages="Test message",
    )

    agent_config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini")

    # Test context provision (should show tools not available)
    result = await provider.provide_context(
        "test-agent", "FRANCE", context_data, agent_config
    )

    assert result["provider_type"] == "mcp"
    assert result["tools_available"] is False
    assert "MCP tools not available" in result["context_text"]

    logger.info("✓ MCPContextProvider correctly shows tools not available") 