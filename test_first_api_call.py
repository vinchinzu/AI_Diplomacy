#!/usr/bin/env python3
"""
Pytest test file to validate the first API call and step through the first round.
This helps isolate and debug LLM connection issues without running a full game.
"""

import asyncio
import logging
import os
import time
from typing import Dict, List
from unittest.mock import patch 
import pytest
import pytest_asyncio

import dotenv
from diplomacy import Game

# Import our AI diplomacy components
from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.utils import get_valid_orders, gather_possible_orders
from ai_diplomacy.llm_coordinator import LLMCallResult

# Load environment variables
dotenv.load_dotenv()

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GameTestArgs:
    """Test arguments class for GameConfig."""
    def __init__(self, model_id: str = "gemma3:latest", use_mocks: bool = True):
        self.power_name = "FRANCE"
        self.model_id = model_id
        self.num_players = 1
        self.game_id_prefix = "test_api"
        self.game_id = f"test_api_{int(time.time())}"
        self.log_level = "INFO"
        self.log_to_file = True
        self.log_dir = "./test_logs"
        self.perform_planning_phase = False
        self.num_negotiation_rounds = 0
        self.negotiation_style = "simultaneous"
        self.fixed_models = [model_id]
        self.randomize_fixed_models = False
        self.exclude_powers = None
        self.max_years = None
        self.use_mocks = use_mocks
        self.dev_mode = False

@pytest_asyncio.fixture
async def test_environment():
    """Pytest fixture to set up test environment."""
    model_id = "gemma3:latest"
    use_mocks = True  # Always use mocks in tests
    
    args = GameTestArgs(model_id, use_mocks)
    config = GameConfig(args)
    
    # Setup logging
    setup_logging(config)
    
    # Create game and history
    game = Game()
    game_history = GameHistory()
    
    # Initialize agent manager
    agent_manager = AgentManager(config)
    
    return {
        'config': config,
        'game': game,
        'game_history': game_history,
        'agent_manager': agent_manager,
        'model_id': model_id,
        'use_mocks': use_mocks
    }

async def _get_mocked_llm_call_internal(model_id: str, *args, **kwargs):
    """Helper to provide a mocked llm_call_internal behavior."""
    # Default mock orders for FRANCE in S1901M
    mock_response_json_string = '{"orders": ["A PAR H", "A MAR H", "F BRE H"]}'
    
    # llm_call_internal returns a string, and the extraction function looks for "PARSABLE OUTPUT:" pattern
    mock_full_response = f"""Reasoning:
- Mock reasoning for test
- These are test orders for validation

PARSABLE OUTPUT:
{mock_response_json_string}"""
    
    return mock_full_response

@pytest.mark.asyncio
async def test_single_power_initialization(test_environment):
    """Test initializing a single power."""
    env = test_environment
    agent_manager = env['agent_manager']
    model_id = env['model_id']
    power_name = "FRANCE"
    
    logger.info(f"Testing initialization of power: {power_name}")
    
    # Assign model to single power
    powers_and_models = {power_name: model_id}
    agent_manager.initialize_agents(powers_and_models)
    
    assert power_name in agent_manager.agents, f"Failed to initialize agent for {power_name}"
    
    agent = agent_manager.agents[power_name]
    assert agent.model_id == model_id, f"Model ID mismatch: expected {model_id}, got {agent.model_id}"
    assert agent.goals is not None, "Agent goals should not be None"
    assert agent.relationships is not None, "Agent relationships should not be None"
    
    logger.info(f"✅ Successfully initialized agent for {power_name}")

@pytest.mark.asyncio
async def test_first_api_call(test_environment):
    """Test the first API call for order generation."""
    env = test_environment
    game = env['game']
    game_history = env['game_history']
    agent_manager = env['agent_manager']
    config = env['config']
    model_id = env['model_id']
    power_name = "FRANCE"
    
    logger.info(f"Testing first API call for {power_name} (Mocks: {env['use_mocks']})...")
    
    # Initialize agent first
    powers_and_models = {power_name: model_id}
    agent_manager.initialize_agents(powers_and_models)
    
    assert power_name in agent_manager.agents, f"Agent for {power_name} not initialized"
    
    agent = agent_manager.agents[power_name]
    
    # Set up game state using correct API
    game.set_current_phase("S1901M")
    if not game.get_units(power_name):
        if power_name == "FRANCE":
            game.set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
    
    board_state = game.get_state()
    current_phase = game.get_current_phase()
    
    # Get possible orders for this power
    possible_orders = gather_possible_orders(game, power_name)
    
    # Create log file path
    log_file_path = os.path.join(config.game_id_specific_log_dir, "test_api_calls.csv")
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    
    logger.info(f"🚀 Making first API call to {model_id} for {power_name}...")
    start_time = time.time()
    
    orders_callable = get_valid_orders(
        game=game,
        model_id=model_id,
        agent_system_prompt=agent.system_prompt,
        board_state=board_state,
        power_name=power_name,
        possible_orders=possible_orders,
        game_history=game_history,
        game_id=config.game_id,
        config=config,
        agent_goals=agent.goals,
        agent_relationships=agent.relationships,
        agent_private_diary_str=agent.format_private_diary_for_prompt(),
        log_file_path=log_file_path,
        phase=current_phase
    )

    # Use mocks for testing
    with patch('ai_diplomacy.llm_coordinator.llm_call_internal', 
               side_effect=lambda *args, **kwargs: _get_mocked_llm_call_internal(model_id, *args, **kwargs)):
        orders = await orders_callable
        
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"✅ API call completed in {duration:.2f} seconds")
    logger.info(f"Generated orders: {orders}")
    
    # Validate orders
    assert orders is not None, "Orders should not be None"
    assert len(orders) > 0, "Should generate at least one order"
    
    # Check that mocked orders match expected
    expected_orders = ["A PAR H", "A MAR H", "F BRE H"]
    assert sorted(orders) == sorted(expected_orders), f"Expected {expected_orders}, got {orders}"
    
    logger.info(f"✅ Successfully generated {len(orders)} orders")

@pytest.mark.asyncio
async def test_multiple_sequential_calls(test_environment):
    """Test multiple sequential API calls to check for consistency."""
    env = test_environment
    power_name = "FRANCE"
    num_calls = 3
    
    logger.info(f"Testing {num_calls} sequential API calls for {power_name} (Mocks: {env['use_mocks']})...")
    
    # Initialize agent first
    agent_manager = env['agent_manager']
    model_id = env['model_id']
    powers_and_models = {power_name: model_id}
    agent_manager.initialize_agents(powers_and_models)
    
    success_count = 0
    for i in range(num_calls):
        logger.info(f"--- API Call {i+1}/{num_calls} ---")
        try:
            # Run the same test as test_first_api_call but without the initialization
            await _run_single_api_call_test(env, power_name)
            success_count += 1
            logger.info(f"✅ Call {i+1} succeeded")
        except Exception as e:
            logger.warning(f"⚠️  Call {i+1} failed: {e}")
        
        if i < num_calls - 1:
            await asyncio.sleep(0.1)  # Short sleep for mocks
    
    success_rate = (success_count / num_calls) * 100
    logger.info(f"📊 Sequential test results: {success_count}/{num_calls} successful ({success_rate:.1f}%)")
    
    assert success_count == num_calls, f"Expected all {num_calls} calls to succeed, but only {success_count} did"

async def _run_single_api_call_test(env, power_name: str):
    """Helper function to run a single API call test."""
    game = env['game']
    game_history = env['game_history']
    agent_manager = env['agent_manager']
    config = env['config']
    model_id = env['model_id']
    
    assert power_name in agent_manager.agents, f"Agent for {power_name} not initialized"
    
    agent = agent_manager.agents[power_name]
    
    # Set up game state using correct API
    game.set_current_phase("S1901M")
    if not game.get_units(power_name):
        if power_name == "FRANCE":
            game.set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
    
    board_state = game.get_state()
    current_phase = game.get_current_phase()
    possible_orders = gather_possible_orders(game, power_name)
    
    log_file_path = os.path.join(config.game_id_specific_log_dir, "test_api_calls.csv")
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    
    orders_callable = get_valid_orders(
        game=game,
        model_id=model_id,
        agent_system_prompt=agent.system_prompt,
        board_state=board_state,
        power_name=power_name,
        possible_orders=possible_orders,
        game_history=game_history,
        game_id=config.game_id,
        config=config,
        agent_goals=agent.goals,
        agent_relationships=agent.relationships,
        agent_private_diary_str=agent.format_private_diary_for_prompt(),
        log_file_path=log_file_path,
        phase=current_phase
    )

    with patch('ai_diplomacy.llm_coordinator.llm_call_internal', 
               side_effect=lambda *args, **kwargs: _get_mocked_llm_call_internal(model_id, *args, **kwargs)):
        orders = await orders_callable
    
    assert orders is not None and len(orders) > 0, "Should generate valid orders"
    return orders

@pytest.mark.asyncio
async def test_concurrent_calls(test_environment):
    """Test concurrent API calls to check for race conditions."""
    env = test_environment
    powers = ["FRANCE", "GERMANY"]
    max_concurrent = 2
    
    logger.info(f"Testing concurrent API calls for powers: {powers} (Mocks: {env['use_mocks']})...")
    
    # Initialize all specified powers
    agent_manager = env['agent_manager']
    model_id = env['model_id']
    
    # Initialize agents for all powers at once
    powers_and_models = {power: model_id for power in powers}
    agent_manager.initialize_agents(powers_and_models)
    
    # Set up units for each power
    for power in powers:
        if power == "FRANCE":
            env['game'].set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
        elif power == "GERMANY":
            env['game'].set_units("GERMANY", ["A BER", "A MUN", "F KIE"])
    
    tasks = []
    for power_name in powers[:max_concurrent]:
        task = asyncio.create_task(_run_single_api_call_test(env, power_name))
        tasks.append((power_name, task))
    
    logger.info(f"🚀 Starting {len(tasks)} concurrent API calls...")
    start_time = time.time()
    
    results = {}
    for power_name, task in tasks:
        try:
            orders = await task
            results[power_name] = True
            logger.info(f"✅ {power_name}: Success")
        except Exception as e:
            results[power_name] = False
            logger.error(f"❌ {power_name}: Failed - {e}")
    
    end_time = time.time()
    duration = end_time - start_time
    success_count = sum(1 for res in results.values() if res)
    total_count = len(results)
    
    logger.info(f"📊 Concurrent test results: {success_count}/{total_count} successful in {duration:.2f}s")
    
    assert success_count == total_count, f"Expected all {total_count} concurrent calls to succeed, but only {success_count} did"

# Keep the original main function for backward compatibility
async def main():
    """Main test function for backward compatibility."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test first API call functionality")
    parser.add_argument("--model", default="gemma3:latest", help="Model ID to test.")
    parser.add_argument("--power", default="FRANCE", help="Power to test.")
    parser.add_argument("--test", choices=["all", "single", "sequential", "concurrent"], 
                       default="all", help="Which test to run.")
    parser.add_argument("--use-mocks", action="store_true", default=True, 
                       help="Use mocked LLM responses instead of live calls.")
    
    args = parser.parse_args()
    
    # For standalone execution, run tests manually
    logger.info("Running tests in standalone mode. Use 'pytest test_first_api_call.py' for proper pytest execution.")
    
    # This is a simplified version for standalone execution
    # The proper way is to use pytest
    
if __name__ == "__main__":
    asyncio.run(main())