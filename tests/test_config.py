import logging
import pytest
from ai_diplomacy.services.config import (
    AgentConfig,
    GameConfig,
    DiplomacyConfig,
    resolve_context_provider,
)
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.llm_agent import LLMAgent

logger = logging.getLogger(__name__)


@pytest.mark.unit
def test_config_context_provider_field():  # Renamed to avoid clash if merged later
    """Test that agent configs specify context providers correctly."""
    logger.info("Testing context provider configuration field...")

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

    logger.info("✓ Context provider configuration field working correctly")


@pytest.mark.unit
def test_resolve_context_provider_logic():  # Renamed
    """Test resolve_context_provider function logic."""
    logger.info("Testing resolve_context_provider logic...")
    # Tool-capable model should resolve to MCP
    tool_config = AgentConfig(
        country="RUSSIA", type="llm", model_id="gpt-4o", context_provider="auto"
    )
    resolved_tool = resolve_context_provider(tool_config)
    assert resolved_tool == "mcp"

    # Non-tool model should resolve to inline
    simple_config = AgentConfig(
        country="ITALY", type="llm", model_id="ollama/llama3", context_provider="auto"
    )
    resolved_simple = resolve_context_provider(simple_config)
    assert resolved_simple == "inline"

    # Explicitly set should not be changed by resolve
    explicit_inline = AgentConfig(
        country="AUSTRIA", type="llm", model_id="gpt-4o", context_provider="inline"
    )
    resolved_explicit_inline = resolve_context_provider(explicit_inline)
    assert resolved_explicit_inline == "inline"

    explicit_mcp = AgentConfig(
        country="TURKEY", type="llm", model_id="ollama/llama3", context_provider="mcp"
    )
    resolved_explicit_mcp = resolve_context_provider(explicit_mcp)
    assert resolved_explicit_mcp == "mcp"

    logger.info("✓ resolve_context_provider logic working correctly")


@pytest.mark.unit
def test_full_config_integration_context_providers():  # Renamed
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
    # Note: AgentFactory internally calls resolve_context_provider during agent creation
    factory = AgentFactory()
    agents = factory.create_agents_from_config(config, "test-game")

    assert len(agents) == 4
    assert isinstance(agents["FRANCE"], LLMAgent)
    # Factory resolves 'inline' to 'inline'
    assert agents["FRANCE"].resolved_context_provider_type == "inline"

    assert isinstance(agents["GERMANY"], LLMAgent)
    # Factory resolves 'mcp' for 'gpt-4o' to 'mcp', but MCPContextProvider.is_available() is false
    # so it falls back to 'inline'.
    assert (
        agents["GERMANY"].resolved_context_provider_type == "inline"
    )  # Fallback because MCP not available

    assert isinstance(agents["ENGLAND"], LLMAgent)
    # Factory resolves 'auto' for 'claude-3-haiku' (non-tool) to 'inline'
    assert (
        agents["ENGLAND"].resolved_context_provider_type == "inline"
    )  # Resolved to inline for non-tool model

    # Scripted agent doesn't have context providers
    assert agents["RUSSIA"].get_agent_info()["type"] == "ScriptedAgent"
    assert not hasattr(agents["RUSSIA"], "resolved_context_provider_type")

    logger.info(
        "✓ Full configuration integration with context providers working correctly"
    )
