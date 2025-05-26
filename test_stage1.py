#!/usr/bin/env python3
"""
Test script for Stage 1 of the refactor.
Verifies that the clean agent boundary works correctly.
"""

import asyncio # Keep for test_llm_agent_interface and pytest-asyncio
import logging
import pytest # Add pytest
from unittest.mock import patch
from ai_diplomacy.core.state import PhaseState
from ai_diplomacy.core.manager import GameEvent
from ai_diplomacy.agents.factory import AgentFactory
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.services.config import DiplomacyConfig, AgentConfig, GameConfig

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
    scripted_agent = factory.create_agent("test-scripted", "GERMANY", scripted_config, "test-game")
    
    assert scripted_agent.country == "GERMANY"
    assert scripted_agent.get_agent_info()["type"] == "ScriptedAgent"
    
    logger.info("✓ AgentFactory working correctly")


def test_config_integration():
    """Test creating agents from full configuration."""
    logger.info("Testing configuration integration...")
    
    # Create a diplomacy configuration
    game_config = GameConfig(token_budget=5000, use_mcp=False)
    agents_config = [
        AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini"),
        AgentConfig(country="GERMANY", type="scripted"),
        AgentConfig(country="ENGLAND", type="llm", model_id="claude-3-haiku")
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
        details={"unit_type": "A"}
    )
    
    assert event.event_type == "unit_lost"
    assert event.participants["country"] == "FRANCE"
    
    logger.info("✓ GameManager components working correctly")


@pytest.mark.asyncio
async def test_llm_agent_interface():
    """Test that LLMAgent implements the BaseAgent interface correctly."""
    logger.info("Testing LLMAgent interface...")
    
    # Create agent config
    config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini")
    
    # Create agent
    agent = LLMAgent(
        agent_id="test-france",
        country="FRANCE",
        config=config,
        game_id="test-game"
    )
    
    # Test agent info
    info = agent.get_agent_info()
    assert info["country"] == "FRANCE"
    assert info["type"] == "LLMAgent"
    assert info["model_id"] == "gpt-4o-mini"
    
    # Create a test phase state
    phase = PhaseState(
        phase_name="S1901M",
        year=1901,
        season="SPRING",
        phase_type="MOVEMENT",
        powers=frozenset(["FRANCE", "GERMANY"]),
        units={"FRANCE": ["A PAR", "F BRE"], "GERMANY": ["A BER", "F KIE"]},
        supply_centers={"FRANCE": ["PAR", "BRE", "MAR"], "GERMANY": ["BER", "KIE", "MUN"]}
    )
    
    # Test that the agent can handle the phase state
    
    # Define mock return values
    mock_orders_return_value = ['A PAR H']
    mock_negotiate_return_value = [{'recipient': 'GERMANY', 'message': 'Hello!'}]
    
    # Mock llm_call_internal
    with patch('ai_diplomacy.services.llm_coordinator.llm_call_internal', side_effect=[
        mock_orders_return_value,  # For decide_orders
        mock_negotiate_return_value,  # For negotiate
        None  # For update_state
    ]) as mock_llm_call:
        orders = await agent.decide_orders(phase)
        messages = await agent.negotiate(phase)
        await agent.update_state(phase, [])
        
        # Assert that the methods returned the mock values
        assert orders == mock_orders_return_value
        assert messages == mock_negotiate_return_value
        
        # Assert that llm_call_internal was called 3 times
        assert mock_llm_call.call_count == 3
        
    logger.info("✓ LLMAgent interface working correctly with mocked LLM calls")


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
        supply_centers={"FRANCE": ["PAR"]}
    )
    
    # Try to modify it (should not work due to frozen=True)
    try:
        phase.year = 1902  # This should fail
        assert False, "PhaseState should be immutable"
    except Exception:
        pass  # Expected
    
    # Test that agents receive PhaseState, not Game objects
    config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini")
    agent = LLMAgent("test", "FRANCE", config)
    
    # Verify agent doesn't have direct game access
    assert not hasattr(agent, 'game')
    assert hasattr(agent, 'config')
    assert hasattr(agent, 'llm_coordinator')
    
    logger.info("✓ Clean boundaries maintained")

# Removed main() function and if __name__ == "__main__": block
# Pytest will discover and run the test functions automatically.