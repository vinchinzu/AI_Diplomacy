import pytest
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.services.config import DiplomacyConfig, AgentConfig, GameConfig

@pytest.mark.unit
def test_agent_factory():
    """Test the agent factory creation."""
    factory = AgentFactory()

    # Test LLM agent creation
    llm_config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini")
    llm_agent = factory.create_agent("test-llm", "FRANCE", llm_config, "test-game")

    assert isinstance(llm_agent, LLMAgent)
    assert llm_agent.country == "FRANCE"
    assert llm_agent.config.model_id == "gpt-4o-mini"

    # Test scripted agent creation
    scripted_config = AgentConfig(country="GERMANY", type="scripted")
    scripted_agent = factory.create_agent(
        "test-scripted", "GERMANY", scripted_config, "test-game"
    )

    assert scripted_agent.country == "GERMANY"
    assert scripted_agent.get_agent_info()["type"] == "ScriptedAgent"


@pytest.mark.unit
def test_create_agents_from_config_with_context_providers():
    """Test creating agents from a full configuration, focusing on context provider resolution."""
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
            model_id="claude-3-haiku", # non-tool model
            context_provider="auto",
        ),
        AgentConfig(country="RUSSIA", type="scripted"),
    ]
    config = DiplomacyConfig(game=game_config, agents=agents_config)

    # Create agents from config
    factory = AgentFactory()
    agents = factory.create_agents_from_config(config, "test-game-stage2-integration")

    assert len(agents) == 4
    assert isinstance(agents["FRANCE"], LLMAgent)
    assert agents["FRANCE"].resolved_context_provider_type == "inline"

    assert isinstance(agents["GERMANY"], LLMAgent)
    # MCPContextProvider is not available (no client), so factory's get_provider("mcp")
    # (called by resolve_context_provider via create_llm_agent) should fallback to InlineContextProvider.
    assert agents["GERMANY"].resolved_context_provider_type == "inline"  # Fallback

    assert isinstance(agents["ENGLAND"], LLMAgent)
    # claude-3-haiku is not tool-capable by default, 'auto' should resolve to 'inline'.
    assert (
        agents["ENGLAND"].resolved_context_provider_type == "inline"
    )

    # Scripted agent doesn't have context providers
    assert agents["RUSSIA"].get_agent_info()["type"] == "ScriptedAgent"
    assert not hasattr(agents["RUSSIA"], "resolved_context_provider_type")
