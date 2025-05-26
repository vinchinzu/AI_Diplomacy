#!/usr/bin/env python3
"""
Test script for Stage 2 of the refactor.
Verifies that the pluggable context provider system works correctly.
"""

import logging
import pytest # Add pytest
from unittest.mock import patch
from ai_diplomacy.core.state import PhaseState
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.agents.base import Order # Import Order
from ai_diplomacy.services.config import DiplomacyConfig, AgentConfig, GameConfig
from ai_diplomacy.services.context_provider import (
    ContextProviderFactory, 
    InlineContextProvider, 
    MCPContextProvider,
    ContextData
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
        supply_centers={"FRANCE": ["PAR", "BRE", "MAR"], "GERMANY": ["BER", "KIE", "MUN"]}
    )
    
    # Create test context data
    context_data = ContextData(
        phase_state=phase_state,
        possible_orders={"A PAR": ["A PAR H", "A PAR-BUR"], "F BRE": ["F BRE H", "F BRE-ENG"]},
        recent_messages="France to Germany: Hello!",
        strategic_analysis="Paris is well defended."
    )
    
    # Create test agent config
    agent_config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini")
    
    # Test context provision
    result = await provider.provide_context("test-agent", "FRANCE", context_data, agent_config)
    
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
        supply_centers={"FRANCE": ["PAR", "BRE", "MAR"], "GERMANY": ["BER", "KIE", "MUN"]}
    )
    
    context_data = ContextData(
        phase_state=phase_state,
        possible_orders={"A PAR": ["A PAR H", "A PAR-BUR"]},
        recent_messages="Test message"
    )
    
    agent_config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini")
    
    # Test context provision (should show tools not available)
    result = await provider.provide_context("test-agent", "FRANCE", context_data, agent_config)
    
    assert result["provider_type"] == "mcp"
    assert result["tools_available"] is False
    assert "MCP tools not available" in result["context_text"]
    
    logger.info("✓ MCPContextProvider correctly shows tools not available")


def test_config_context_provider():
    """Test that agent configs specify context providers correctly."""
    logger.info("Testing context provider configuration...")
    
    # Test explicit inline config
    inline_config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini", context_provider="inline")
    assert inline_config.context_provider == "inline"
    
    # Test explicit MCP config
    mcp_config = AgentConfig(country="GERMANY", type="llm", model_id="claude-3-haiku", context_provider="mcp")
    assert mcp_config.context_provider == "mcp"
    
    # Test auto config (default)
    auto_config = AgentConfig(country="ENGLAND", type="llm", model_id="gpt-4o")
    assert auto_config.context_provider == "auto"
    
    # Test resolve_context_provider function
    from ai_diplomacy.services.config import resolve_context_provider
    
    # Tool-capable model should resolve to MCP
    tool_config = AgentConfig(country="RUSSIA", type="llm", model_id="gpt-4o", context_provider="auto")
    resolved = resolve_context_provider(tool_config)
    assert resolved == "mcp"
    
    # Non-tool model should resolve to inline
    simple_config = AgentConfig(country="ITALY", type="llm", model_id="ollama/llama3", context_provider="auto")
    resolved = resolve_context_provider(simple_config)
    assert resolved == "inline"
    
    logger.info("✓ Context provider configuration working correctly")


@pytest.mark.asyncio
async def test_agent_with_context_providers():
    """Test that agents work correctly with different context providers."""
    logger.info("Testing agents with context providers...")
    
    # Create agents with different context provider configs
    inline_config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini", context_provider="inline")
    mcp_config = AgentConfig(country="GERMANY", type="llm", model_id="gpt-4o", context_provider="mcp")
    auto_config = AgentConfig(country="ENGLAND", type="llm", model_id="claude-3-haiku", context_provider="auto")
    
    factory = AgentFactory()
    
    # Create agents
    inline_agent = factory.create_agent("inline-test", "FRANCE", inline_config, "test-game")
    mcp_agent = factory.create_agent("mcp-test", "GERMANY", mcp_config, "test-game")
    auto_agent = factory.create_agent("auto-test", "ENGLAND", auto_config, "test-game")
    
    # Check that agents have correct context providers
    assert isinstance(inline_agent, LLMAgent)
    assert inline_agent.resolved_context_provider_type == "inline"
    
    assert isinstance(mcp_agent, LLMAgent)
    assert mcp_agent.resolved_context_provider_type == "inline"  # Should fallback since MCP not available
    
    assert isinstance(auto_agent, LLMAgent)
    assert auto_agent.resolved_context_provider_type == "inline"  # Should fallback since MCP not available
    
    # Create test phase state
    phase_state = PhaseState(
        phase_name="S1901M",
        year=1901,
        season="SPRING",
        phase_type="MOVEMENT",
        powers=frozenset(["FRANCE", "GERMANY", "ENGLAND"]),
        units={"FRANCE": ["A PAR"], "GERMANY": ["A BER"], "ENGLAND": ["F LON"]},
        supply_centers={"FRANCE": ["PAR"], "GERMANY": ["BER"], "ENGLAND": ["LON"]}
    )
    
    # Test that agents can call decide_orders with context providers
    mock_llm_orders_string_output = '{"orders": ["A PAR H"]}'
    expected_agent_orders = [Order("A PAR H")]

    # Test inline_agent
    with patch('ai_diplomacy.services.llm_coordinator.llm_call_internal', return_value=mock_llm_orders_string_output) as mock_llm_call_inline:
        orders = await inline_agent.decide_orders(phase_state)
        assert orders == expected_agent_orders
        assert mock_llm_call_inline.call_count == 1
        logger.info(f"Inline agent generated {len(orders)} orders with mock")

    # Test mcp_agent
    with patch('ai_diplomacy.services.llm_coordinator.llm_call_internal', return_value=mock_llm_orders_string_output) as mock_llm_call_mcp:
        orders = await mcp_agent.decide_orders(phase_state)
        assert orders == expected_agent_orders
        assert mock_llm_call_mcp.call_count == 1 
        logger.info(f"MCP agent generated {len(orders)} orders with mock (expected fallback to inline)")

    # Test auto_agent
    with patch('ai_diplomacy.services.llm_coordinator.llm_call_internal', return_value=mock_llm_orders_string_output) as mock_llm_call_auto:
        orders = await auto_agent.decide_orders(phase_state)
        assert orders == expected_agent_orders
        assert mock_llm_call_auto.call_count == 1
        logger.info(f"Auto agent generated {len(orders)} orders with mock (expected fallback to inline)")
    
    logger.info("✓ Agents working correctly with mocked context providers and LLM calls")


def test_full_config_integration():
    """Test full configuration integration with context providers."""
    logger.info("Testing full configuration integration...")
    
    # Create a full diplomacy configuration with mixed context providers
    game_config = GameConfig(token_budget=5000, use_mcp=True)
    agents_config = [
        AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini", context_provider="inline"),
        AgentConfig(country="GERMANY", type="llm", model_id="gpt-4o", context_provider="mcp"),
        AgentConfig(country="ENGLAND", type="llm", model_id="claude-3-haiku", context_provider="auto"),
        AgentConfig(country="RUSSIA", type="scripted", context_provider="inline"),  # Scripted doesn't use context providers
    ]
    config = DiplomacyConfig(game=game_config, agents=agents_config)
    
    # Create agents from config
    factory = AgentFactory()
    agents = factory.create_agents_from_config(config, "test-game")
    
    assert len(agents) == 4
    assert "FRANCE" in agents
    assert "GERMANY" in agents
    assert "ENGLAND" in agents
    assert "RUSSIA" in agents
    
    # Check that LLM agents have correct context providers
    assert isinstance(agents["FRANCE"], LLMAgent)
    assert agents["FRANCE"].resolved_context_provider_type == "inline"
    
    assert isinstance(agents["GERMANY"], LLMAgent)  
    assert agents["GERMANY"].resolved_context_provider_type == "inline"  # Fallback since MCP not available
    
    assert isinstance(agents["ENGLAND"], LLMAgent)
    assert agents["ENGLAND"].resolved_context_provider_type == "inline"  # Should fallback since MCP not available
    
    # Scripted agent doesn't have context providers
    assert agents["RUSSIA"].get_agent_info()["type"] == "ScriptedAgent"
    
    logger.info("✓ Full configuration integration working correctly")

# Removed main() function and if __name__ == "__main__": block
# Pytest will discover and run the test functions automatically.