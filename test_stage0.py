#!/usr/bin/env python3
"""
Test script for Stage 0 of the refactor.
Verifies that the new directory structure and basic components work.
"""

import asyncio
import logging
from ai_diplomacy.core.state import PhaseState

from ai_diplomacy.agents.scripted_agent import ScriptedAgent
from ai_diplomacy.services.config import DiplomacyConfig, AgentConfig, GameConfig
from ai_diplomacy.services.llm_coordinator import LLMCoordinator

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_core_state():
    """Test PhaseState creation."""
    logger.info("Testing PhaseState creation...")
    
    # Create a minimal test phase state
    phase = PhaseState(
        phase_name="S1901M",
        year=1901,
        season="SPRING",
        phase_type="MOVEMENT",
        powers=frozenset(["FRANCE", "GERMANY"]),
        units={"FRANCE": ["A PAR", "F BRE"], "GERMANY": ["A BER", "F KIE"]},
        supply_centers={"FRANCE": ["PAR", "BRE", "MAR"], "GERMANY": ["BER", "KIE", "MUN"]}
    )
    
    assert phase.get_center_count("FRANCE") == 3
    assert phase.get_center_count("GERMANY") == 3
    assert not phase.is_power_eliminated("FRANCE")
    
    logger.info("✓ PhaseState working correctly")


async def test_scripted_agent():
    """Test scripted agent functionality."""
    logger.info("Testing ScriptedAgent...")
    
    agent = ScriptedAgent("test-france", "FRANCE", "neutral")
    
    # Create test phase state
    phase = PhaseState(
        phase_name="S1901M",
        year=1901,
        season="SPRING",
        phase_type="MOVEMENT",
        powers=frozenset(["FRANCE", "GERMANY"]),
        units={"FRANCE": ["A PAR", "F BRE"], "GERMANY": ["A BER", "F KIE"]},
        supply_centers={"FRANCE": ["PAR", "BRE", "MAR"], "GERMANY": ["BER", "KIE", "MUN"]}
    )
    
    # Test order generation
    orders = await agent.decide_orders(phase)
    logger.info(f"Generated {len(orders)} orders: {[str(o) for o in orders]}")
    
    # Test message generation
    messages = await agent.negotiate(phase)
    logger.info(f"Generated {len(messages)} messages")
    
    # Test state update
    await agent.update_state(phase, [])
    
    logger.info("✓ ScriptedAgent working correctly")


def test_config():
    """Test configuration system."""
    logger.info("Testing configuration system...")
    
    # Test creating config from scratch
    game_config = GameConfig(token_budget=5000, use_mcp=False)
    agent_config = AgentConfig(country="FRANCE", type="llm", model_id="gpt-4o-mini")
    config = DiplomacyConfig(game=game_config, agents=[agent_config])
    
    assert config.game.token_budget == 5000
    agent_config = config.get_agent_config("FRANCE")
    assert agent_config is not None
    assert agent_config.model_id == "gpt-4o-mini"
    assert len(config.get_llm_agents()) == 1
    
    logger.info("✓ Configuration system working correctly")


def test_llm_coordinator():
    """Test LLM coordinator initialization."""
    logger.info("Testing LLM coordinator...")
    
    # Just test initialization for now
    coordinator = LLMCoordinator()
    assert coordinator is not None
    
    logger.info("✓ LLM coordinator initialized correctly")


async def main():
    """Run all tests."""
    logger.info("Starting Stage 0 tests...")
    
    try:
        test_core_state()
        await test_scripted_agent()
        test_config()
        test_llm_coordinator()
        
        logger.info("🎉 All Stage 0 tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1) 