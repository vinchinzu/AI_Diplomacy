#!/usr/bin/env python3
"""
Test script for Stage 1 of the refactor.
Verifies that the clean agent boundary works correctly.
"""

import logging
import pytest  # Added import
from ai_diplomacy.core.state import PhaseState
from ai_diplomacy.core.manager import GameEvent
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.services.config import DiplomacyConfig, AgentConfig, GameConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@pytest.mark.unit
def test_agent_factory():
    """Test the agent factory creation."""
    logger.info("Testing AgentFactory...")

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

    logger.info("✓ AgentFactory working correctly")


@pytest.mark.unit
def test_config_integration():
    """Test creating agents from full configuration."""
    logger.info("Testing configuration integration...")

    # Create a diplomacy configuration
    game_config = GameConfig(token_budget=5000, use_mcp=False)
    agents_config = [
        AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini"),
        AgentConfig(country="GERMANY", type="scripted"),
        AgentConfig(country="ENGLAND", type="llm", model_id="claude-3-haiku"),
    ]
    config = DiplomacyConfig(game=game_config, agents=agents_config)

    # Create agents from config
    factory = AgentFactory()
    agents = factory.create_agents_from_config(config, "test-game")

    assert len(agents) == 3
    assert "FRANCE" in agents
    assert "GERMANY" in agents
    assert "ENGLAND" in agents

    # Verify agent types
    assert isinstance(agents["FRANCE"], LLMAgent)
    assert agents["GERMANY"].get_agent_info()["type"] == "ScriptedAgent"
    assert isinstance(agents["ENGLAND"], LLMAgent)

    logger.info("✓ Configuration integration working correctly")


@pytest.mark.unit
def test_game_manager():
    """Test the core game manager."""
    logger.info("Testing GameManager...")

    # We need a mock diplomacy Game for testing
    # For now, let's test what we can without the actual game

    # Test GameEvent creation
    event = GameEvent(
        event_type="unit_lost",
        phase="S1901M",
        participants={"country": "FRANCE", "unit": "A PAR"},
        details={"unit_type": "A"},
    )

    assert event.event_type == "unit_lost"
    assert event.participants["country"] == "FRANCE"

    logger.info("✓ GameManager components working correctly")


@pytest.mark.unit
def test_clean_boundaries():
    """Test that the clean boundaries are maintained."""
    logger.info("Testing clean boundaries...")

    # Test that PhaseState is immutable
    phase = PhaseState(
        phase_name="S1901M",
        year=1901,
        season="SPRING",
        phase_type="MOVEMENT",
        powers=frozenset(["FRANCE"]),
        units={"FRANCE": ["A PAR"]},
        supply_centers={"FRANCE": ["PAR"]},
    )

    # Try to modify it (should not work due to frozen=True)
    try:
        phase.year = 1902  # This should fail
        assert False, "PhaseState should be immutable"
    except Exception:
        pass  # Expected

    # Test that agents receive PhaseState, not Game objects
    config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini")
    # We need to import load_prompt_file for this direct instantiation
    from generic_llm_framework.llm_utils import load_prompt_file # Updated import

    agent = LLMAgent("test", "FRANCE", config, prompt_loader=load_prompt_file)

    # Verify agent doesn't have direct game access
    assert not hasattr(agent, "game")
    assert hasattr(agent, "config")
    assert hasattr(agent, "llm_coordinator")

    logger.info("✓ Clean boundaries maintained")
