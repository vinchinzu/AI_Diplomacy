#!/usr/bin/env python3
"""
Test script for Stage 2 of the refactor.
Verifies that the pluggable context provider system works correctly.
"""

import logging
import pytest  # Add pytest
from unittest.mock import patch, AsyncMock # Added AsyncMock
from ai_diplomacy.core.state import PhaseState
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.agents.base import Order  # Import Order
from ai_diplomacy.services.config import DiplomacyConfig, AgentConfig, GameConfig
from ai_diplomacy.services.context_provider import (
    ContextProviderFactory,
    InlineContextProvider,
    MCPContextProvider,
    ContextData,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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

@pytest.mark.unit
def test_config_context_provider():
    """Test that agent configs specify context providers correctly."""
    logger.info("Testing context provider configuration...")

    # Test explicit inline config
    inline_config = AgentConfig(
        country="FRANCE", type="llm", model_id="gpt-4o-mini", context_provider="inline"
    )
    assert inline_config.context_provider == "inline"

    # Test explicit MCP config
    mcp_config = AgentConfig(
        country="GERMANY", type="llm", model_id="claude-3-haiku", context_provider="mcp"
    )
    assert mcp_config.context_provider == "mcp"

    # Test auto config (default)
    auto_config = AgentConfig(country="ENGLAND", type="llm", model_id="gpt-4o")
    assert auto_config.context_provider == "auto"

    # Test resolve_context_provider function
    from ai_diplomacy.services.config import resolve_context_provider

    # Tool-capable model should resolve to MCP
    tool_config = AgentConfig(
        country="RUSSIA", type="llm", model_id="gpt-4o", context_provider="auto"
    )
    resolved = resolve_context_provider(tool_config)
    assert resolved == "mcp"

    # Non-tool model should resolve to inline
    simple_config = AgentConfig(
        country="ITALY", type="llm", model_id="ollama/llama3", context_provider="auto"
    )
    resolved = resolve_context_provider(simple_config)
    assert resolved == "inline"

    logger.info("✓ Context provider configuration working correctly")

@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_with_context_providers():
    """Test that agents work correctly with different context providers."""
    logger.info("Testing agents with context providers...")

    # Create agents with different context provider configs
    inline_config = AgentConfig(
        country="FRANCE", type="llm", model_id="gpt-4o-mini", context_provider="inline"
    )
    mcp_config = AgentConfig(
        country="GERMANY", type="llm", model_id="gpt-4o", context_provider="mcp"
    )
    auto_config = AgentConfig(
        country="ENGLAND",
        type="llm",
        model_id="claude-3-haiku",
        context_provider="auto",
    )

    factory = AgentFactory()

    # Create agents
    inline_agent = factory.create_agent(
        "inline-test", "FRANCE", inline_config, "test-game"
    )
    mcp_agent = factory.create_agent("mcp-test", "GERMANY", mcp_config, "test-game")
    auto_agent = factory.create_agent("auto-test", "ENGLAND", auto_config, "test-game")

    # Check that agents have correct context providers
    assert isinstance(inline_agent, LLMAgent)
    assert inline_agent.resolved_context_provider_type == "inline"

    assert isinstance(mcp_agent, LLMAgent)
    assert (
        mcp_agent.resolved_context_provider_type == "inline"
    )  # Should fallback since MCP not available

    assert isinstance(auto_agent, LLMAgent)
    assert (
        auto_agent.resolved_context_provider_type == "inline"
    )  # Should fallback since MCP not available

    # Create test phase state
    phase_state = PhaseState(
        phase_name="S1901M",
        year=1901,
        season="SPRING",
        phase_type="MOVEMENT",
        powers=frozenset(["FRANCE", "GERMANY", "ENGLAND"]),
        units={"FRANCE": ["A PAR"], "GERMANY": ["A BER"], "ENGLAND": ["F LON"]},
        supply_centers={"FRANCE": ["PAR"], "GERMANY": ["BER"], "ENGLAND": ["LON"]},
    )

    # Test that agents can call decide_orders with context providers
    mock_llm_orders_dict_output_france = {"orders": ["A PAR H"]}
    expected_agent_orders_france = [Order("A PAR H")]

    mock_llm_orders_dict_output_germany = {"orders": ["A BER H"]}
    expected_agent_orders_germany = [Order("A BER H")]

    mock_llm_orders_dict_output_england = {"orders": ["F LON H"]}
    expected_agent_orders_england = [Order("F LON H")]

    # Test inline_agent (FRANCE)
    mock_custom_llm_caller_inline = AsyncMock(return_value=mock_llm_orders_dict_output_france)
    inline_agent.llm_caller_override = mock_custom_llm_caller_inline
    orders = await inline_agent.decide_orders(phase_state)
    assert orders == expected_agent_orders_france
    mock_custom_llm_caller_inline.assert_called_once()
    assert mock_custom_llm_caller_inline.call_args is not None
    called_args_kwargs_inline = mock_custom_llm_caller_inline.call_args[1]
    prompt_text_inline = called_args_kwargs_inline["prompt"]
    assert "Game Context and Relevant Information:" in prompt_text_inline
    assert "=== YOUR POSSIBLE ORDERS ===" in prompt_text_inline # Default from InlineContextProvider

    # Test mcp_agent (GERMANY)
    mock_custom_llm_caller_mcp = AsyncMock(return_value=mock_llm_orders_dict_output_germany)
    mcp_agent.llm_caller_override = mock_custom_llm_caller_mcp
    orders = await mcp_agent.decide_orders(phase_state)
    assert orders == expected_agent_orders_germany
    mock_custom_llm_caller_mcp.assert_called_once()
    assert mock_custom_llm_caller_mcp.call_args is not None
    called_args_kwargs_mcp = mock_custom_llm_caller_mcp.call_args[1]
    prompt_text_mcp = called_args_kwargs_mcp["prompt"]
    assert "Game Context and Relevant Information:" in prompt_text_mcp
    assert "=== YOUR POSSIBLE ORDERS ===" in prompt_text_mcp

    # Test auto_agent (ENGLAND)
    mock_custom_llm_caller_auto = AsyncMock(return_value=mock_llm_orders_dict_output_england)
    auto_agent.llm_caller_override = mock_custom_llm_caller_auto
    orders = await auto_agent.decide_orders(phase_state)
    assert orders == expected_agent_orders_england
    mock_custom_llm_caller_auto.assert_called_once()
    assert mock_custom_llm_caller_auto.call_args is not None
    called_args_kwargs_auto = mock_custom_llm_caller_auto.call_args[1]
    prompt_text_auto = called_args_kwargs_auto["prompt"]
    assert "Game Context and Relevant Information:" in prompt_text_auto
    assert "=== YOUR POSSIBLE ORDERS ===" in prompt_text_auto

    logger.info("✓ Agents working correctly with context providers")

@pytest.mark.unit
def test_full_config_integration():
    """Test creating agents from full configuration with context providers."""
    logger.info("Testing full configuration integration with context providers...")

    # Create a full diplomacy configuration with mixed context providers
    game_config = GameConfig(token_budget=5000, use_mcp=False)
    agents_config = [
        AgentConfig(
            country="FRANCE",
            type="llm",
            model_id="gpt-4o-mini",
            context_provider="inline",
        ),
        AgentConfig(
            country="GERMANY", type="llm", model_id="gpt-4o", context_provider="mcp"
        ),
        AgentConfig(
            country="ENGLAND",
            type="llm",
            model_id="claude-3-haiku",
            context_provider="auto",
        ),
        AgentConfig(country="RUSSIA", type="scripted"),
    ]
    config = DiplomacyConfig(game=game_config, agents=agents_config)

    # Create agents from config
    factory = AgentFactory()
    agents = factory.create_agents_from_config(config, "test-game")

    assert len(agents) == 4
    assert isinstance(agents["FRANCE"], LLMAgent)
    assert agents["FRANCE"].resolved_context_provider_type == "inline"

    assert isinstance(agents["GERMANY"], LLMAgent)
    assert (
        agents["GERMANY"].resolved_context_provider_type == "inline"
    )  # Fallback

    assert isinstance(agents["ENGLAND"], LLMAgent)
    assert (
        agents["ENGLAND"].resolved_context_provider_type == "inline"
    )  # Fallback for non-tool model

    # Scripted agent doesn't have context providers
    assert agents["RUSSIA"].get_agent_info()["type"] == "ScriptedAgent"
    assert not hasattr(agents["RUSSIA"], "resolved_context_provider_type")

    logger.info("✓ Full configuration integration with context providers working correctly")
