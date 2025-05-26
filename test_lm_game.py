#!/usr/bin/env python3
"""
Modified version of lm_game.py for testing first round functionality.
This allows stepping through just the first round to validate API calls.
"""

import argparse
import asyncio
import logging
import os
import sys
import time
import traceback
from typing import List
from unittest.mock import patch # Added import

import dotenv
from diplomacy import Game

# New refactored components
from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager
# from ai_diplomacy.game_orchestrator import GamePhaseOrchestrator # Not used in this file
# from ai_diplomacy.game_results import GameResultsProcessor # Not used in this file
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.utils import get_valid_orders, gather_possible_orders, LLMInvalidOutputError # Corrected import


# Suppress warnings
os.environ["GRPC_PYTHON_LOG_LEVEL"] = "40"
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["ABSL_MIN_LOG_LEVEL"] = "2"
os.environ["GRPC_POLL_STRATEGY"] = "poll"

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Diplomacy game first round with configurable parameters."
    )
    parser.add_argument(
        "--power_name", type=str, default=None, 
        help="Name of the primary power to control (e.g., FRANCE). Optional."
    )
    parser.add_argument(
        "--model_ids", type=str, default="gemma3:latest",
        help="Comma-separated list of model IDs for test powers (e.g., 'ollama/llama3,gpt-4o'). Cycles if fewer models than powers."
    )
    parser.add_argument(
        "--num_players", type=int, default=1, 
        help="Number of LLM-controlled players for testing. Default: 1."
    )
    parser.add_argument(
        "--test_powers", type=str, default="FRANCE",
        help="Comma-separated list of powers to test (e.g., 'FRANCE,GERMANY'). Default: FRANCE"
    )
    parser.add_argument(
        "--game_id_prefix", type=str, default="test_game",
        help="Prefix for the game ID. Default: 'test_game'."
    )
    parser.add_argument(
        "--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level. Default: INFO."
    )
    parser.add_argument(
        "--log_to_file", type=lambda x: (str(x).lower() == 'true'), default=True,
        help="Enable/disable file logging. Default: True."
    )
    parser.add_argument(
        "--log_dir", type=str, default="./test_logs",
        help="Base directory for logs. Default: './test_logs'."
    )
    parser.add_argument(
        "--test_type", type=str, default="single_round", 
        choices=["single_round", "order_generation", "sequential_calls", "concurrent_calls"],
        help="Type of test to run. Default: single_round"
    )
    parser.add_argument(
        "--num_sequential", type=int, default=3,
        help="Number of sequential calls to test. Default: 3"
    )
    parser.add_argument(
        "--max_concurrent", type=int, default=2,
        help="Maximum concurrent calls to test. Default: 2"
    )
    parser.add_argument(
        "--use-mocks", action="store_true", default=False, 
        help="Use mocked LLM responses instead of live calls."
    )
    parser.add_argument(
        "--dev_mode", action="store_true", default=True,
        help="Enable development mode for stricter LLM output validation and error handling."
    )
    return parser.parse_args()

class GameTester:
    """Test class for stepping through game functionality."""
    
    def __init__(self, config: GameConfig): # config already has args, including use_mocks
        self.config = config
        # self.use_mocks = config.args.use_mocks # Store use_mocks
        self.game = None
        self.game_history = None
        self.agent_manager = None
        
    async def setup_game(self):
        """Set up the game environment."""
        logger.info(f"Setting up test game environment (Mocks: {self.config.args.use_mocks})...")
        
        # Create game and history
        self.game = Game()
        self.game_history = GameHistory()
        
        # Initialize agent manager
        self.agent_manager = AgentManager(self.config)
        
        logger.info(f"Game setup complete. Current phase: {self.game.current_short_phase}")
        
    async def test_single_round(self, test_powers: List[str]):
        """Test a single round of order generation."""
        logger.info(f"Testing single round for powers: {test_powers} (Mocks: {self.config.args.use_mocks})")
        
        # Initialize agents for test powers
        powers_and_models = {}
        fixed_models_list = self.config.args.fixed_models
        for i, power in enumerate(test_powers):
            powers_and_models[power] = fixed_models_list[i]
            
        self.agent_manager.initialize_agents(powers_and_models)
        
        if not self.agent_manager.agents:
            logger.error("❌ No agents were initialized")
            return False
            
        logger.info(f"✅ Initialized {len(self.agent_manager.agents)} agents")
        
        # Test order generation for each power
        success_count = 0
        total_count = len(test_powers)
        
        for power_name in test_powers:
            if power_name not in self.agent_manager.agents:
                logger.error(f"❌ Agent for {power_name} not found")
                continue
                
            logger.info(f"\n--- Testing {power_name} ---")
            
            try:
                success = await self.test_power_order_generation(power_name)
                if success:
                    success_count += 1
                    logger.info(f"✅ {power_name}: Order generation successful")
                else:
                    logger.error(f"❌ {power_name}: Order generation failed")
                    
            except Exception as e:
                logger.error(f"❌ {power_name}: Exception during test - {e}", exc_info=True)
        
        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
        logger.info(f"\n📊 Single round test results: {success_count}/{total_count} successful ({success_rate:.1f}%)")
        
        return success_count == total_count
    
    
    async def _get_mocked_llm_call_internal(self, power_name_for_mock: str, *args, **kwargs):
        """Helper to provide a mocked llm_call_internal behavior for a specific power."""
        # Default mock orders, assuming S1901M phase for relevant powers
        # This can be made more sophisticated if tests need different responses for different powers
        mock_orders_db = {
            "FRANCE": ["A PAR H", "A MAR H", "F BRE H"],
            "GERMANY": ["A BER H", "A MUN H", "F KIE H"],
            "ENGLAND": ["F LON H", "F EDI H", "A LVP H"],
            # Add other powers as needed for tests
        }
        selected_orders = mock_orders_db.get(power_name_for_mock, [f"A {power_name_for_mock[:3].upper()} H"]) # Generic fallback

        mock_response_json_string = f'{{"orders": {selected_orders}}}'.replace("'", "\"") # Ensure valid JSON
        
        # llm_call_internal returns a string, and the extraction function looks for "PARSABLE OUTPUT:" pattern
        mock_full_response = f"""Reasoning:
- Mock reasoning for {power_name_for_mock}
- These are test orders for validation

PARSABLE OUTPUT:
{mock_response_json_string}"""
        
        return mock_full_response

    async def test_power_order_generation(self, power_name: str) -> bool:
        """Tests order generation for a single power."""
        agent = self.agent_manager.get_agent(power_name)
        if not agent:
            logger.error(f"Agent for {power_name} not found during order generation test.")
            return False

        current_phase = self.game.current_short_phase
        logger.info(f"[{power_name}] Current phase for order generation: {current_phase}")
        
        board_state = self.game.get_state()
        possible_orders = gather_possible_orders(self.game, power_name)
        
        logger.info(f"Possible orders for {power_name}: {list(possible_orders.keys())}")
        
        log_file_path = os.path.join(self.config.game_id_specific_log_dir, "test_orders.csv")
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        logger.info(f"🚀 Generating orders for {power_name}...")
        start_time = time.time()
        
        orders_callable = get_valid_orders(
            game=self.game, model_id=agent.model_id, agent_system_prompt=agent.system_prompt,
            board_state=board_state, power_name=power_name, possible_orders=possible_orders,
            game_history=self.game_history, game_id=self.config.game_id,
            config=self.config, # Pass the full config object
            agent_goals=agent.goals, agent_relationships=agent.relationships,
            agent_private_diary_str=agent.format_private_diary_for_prompt(),
            log_file_path=log_file_path, phase=current_phase
        )

        orders = None
        try:
            if self.config.args.use_mocks:
                # Pass power_name to the mock provider
                async def mock_side_effect(*args, **kwargs):
                    return await self._get_mocked_llm_call_internal(power_name, *args, **kwargs)

                with patch('ai_diplomacy.llm_coordinator.llm_call_internal', 
                           side_effect=mock_side_effect):
                    orders = await orders_callable
            else:
                orders = await orders_callable
        except LLMInvalidOutputError as e: # Specific catch for dev_mode errors
            logger.error(f"DEV_MODE: LLMInvalidOutputError for {power_name} ({agent.model_id}): {e}")
            if e.prompt:
                logger.error(f"  LLM Prompt: {e.prompt}")
            if e.raw_response:
                logger.error(f"  LLM Raw Response: {e.raw_response}")
            if e.proposed_moves:
                logger.error(f"  LLM Proposed Moves: {e.proposed_moves}")
            if e.invalid_moves:
                logger.error(f"  Identified Invalid Moves: {e.invalid_moves}")
            # In dev_mode, this should cause the test to fail or the program to exit.
            # The test_single_round method will already mark this power as failed.
            # If running lm_game.py in dev_mode, it would sys.exit here.
            return False # Ensure this test case for the power is marked as failed
            
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f"⏱️  Order generation for {power_name} took {duration:.2f} seconds")
        logger.info(f"📋 Generated orders for {power_name}: {orders}")

        if self.config.args.use_mocks and orders is not None:
            # Basic check: ensure orders are returned as expected by mock
            # This relies on _get_mocked_llm_call_internal providing consistent mock data
            mock_db = { "FRANCE": ["A PAR H", "A MAR H", "F BRE H"], "GERMANY": ["A BER H", "A MUN H", "F KIE H"], "ENGLAND": ["F LON H", "F EDI H", "A LVP H"]}
            expected_mocked_orders = mock_db.get(power_name, [f"A {power_name[:3].upper()} H"])
            assert sorted(orders) == sorted(expected_mocked_orders), f"Mock orders mismatch for {power_name}: expected {expected_mocked_orders}, got {orders}"
            
        if orders and len(orders) > 0:
            logger.info(f"✅ Successfully generated {len(orders)} orders for {power_name}")
            return True
        else:
            logger.warning(f"⚠️  No orders generated for {power_name}")
            return False

    async def test_sequential_calls(self, power_name: str, num_calls: int):
        """Test multiple sequential API calls."""
        logger.info(f"Testing {num_calls} sequential calls for {power_name} (Mocks: {self.config.args.use_mocks})")
        
        # Initialize single agent
        # Use the first model from the list for sequential tests for this power
        model_to_use_for_power = self.config.args.fixed_models[0] if self.config.args.fixed_models else "gemma3:latest"
        # Find the index of power_name in test_powers to get its assigned model
        try:
            original_test_powers = [p.strip().upper() for p in self.config.args.test_powers.split(',')]
            power_index = original_test_powers.index(power_name)
            model_to_use_for_power = self.config.args.fixed_models[power_index]
        except ValueError:
            logger.warning(f"Power {power_name} not in test_powers list for model assignment in sequential. Using first model.")
            # Fallback to first model if not found (should ideally be in list)
        
        powers_and_models = {power_name: model_to_use_for_power}
        self.agent_manager.initialize_agents(powers_and_models) # Re-initialize for this specific agent
        
        if power_name not in self.agent_manager.agents:
            logger.error(f"❌ Failed to initialize agent for {power_name}")
            return False
        
        success_count = 0
        
        for i in range(num_calls):
            logger.info(f"\n--- Sequential Call {i+1}/{num_calls} ---")
            
            # test_power_order_generation will use self.config.args.use_mocks internally
            success = await self.test_power_order_generation(power_name)
            if success:
                success_count += 1
                logger.info(f"✅ Call {i+1} for {power_name} succeeded")
            else:
                logger.warning(f"⚠️  Call {i+1} for {power_name} failed")
            if i < num_calls - 1:
                await asyncio.sleep(0.1 if self.config.args.use_mocks else 1) # Shorter sleep for mocks
        
        success_rate = (success_count / num_calls) * 100
        logger.info(f"\n📊 Sequential test results for {power_name}: {success_count}/{num_calls} successful ({success_rate:.1f}%)")
        return success_count == num_calls

    async def test_concurrent_calls(self, test_powers: List[str], max_concurrent: int):
        """Test concurrent API calls."""
        logger.info(f"Testing concurrent calls for powers: {test_powers[:max_concurrent]} (Mocks: {self.config.args.use_mocks})")
        
        # Initialize agents for all test powers that will be used in this concurrent test run
        concurrent_powers_to_test = test_powers[:max_concurrent]
        powers_and_models_for_concurrent = {}
        original_test_powers_from_args = [p.strip().upper() for p in self.config.args.test_powers.split(',')]
        
        for power_name in concurrent_powers_to_test:
            try:
                idx = original_test_powers_from_args.index(power_name)
                powers_and_models_for_concurrent[power_name] = self.config.args.fixed_models[idx]
            except ValueError:
                logger.warning(f"Power {power_name} not in original test_powers. Using first fixed model for concurrent test.")
                powers_and_models_for_concurrent[power_name] = self.config.args.fixed_models[0] if self.config.args.fixed_models else "default/model"
        
        self.agent_manager.initialize_agents(powers_and_models_for_concurrent)

        for power_name in concurrent_powers_to_test:
            if power_name not in self.agent_manager.agents:
                logger.error(f"❌ Failed to initialize agent for {power_name} in concurrent test")
                return False
        
        tasks = [
            asyncio.create_task(self.test_power_order_generation(p_name))
            for p_name in concurrent_powers_to_test
        ]
        
        logger.info(f"🚀 Starting {len(tasks)} concurrent API calls...")
        start_time = time.time()
        
        results_list = await asyncio.gather(*tasks) # gather returns list of results
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Map results back to powers for logging
        results_map = {power_name: result for power_name, result in zip(concurrent_powers_to_test, results_list)}
        for p_name, res in results_map.items():
            logger.info(f"🏁 Concurrent result for {p_name}: {'Success' if res else 'Failed'}")

        success_count = sum(1 for res in results_list if res)
        total_count = len(concurrent_powers_to_test)
        
        logger.info(f"\n📊 Concurrent test results: {success_count}/{total_count} successful in {duration:.2f}s")
        return success_count == total_count

async def main():
    args = parse_arguments()
    
    test_powers = [p.strip().upper() for p in args.test_powers.split(',')]
    parsed_model_ids = [m.strip() for m in args.model_ids.split(',')]
    args.model_ids = parsed_model_ids
    
    num_models = len(args.model_ids)
    args.fixed_models = [args.model_ids[i % num_models] for i in range(len(test_powers))]
    
    # Pass use_mocks to GameConfig by adding it to args if not already there by parse_arguments
    if not hasattr(args, 'use_mocks'): # Should be there due to parse_arguments
        args.use_mocks = False 

    args.game_id = f"{args.game_id_prefix}_{int(time.time())}"
    # Ensure other required args for GameConfig are present (they are from parse_arguments)
    args.exclude_powers = None # Default if not parsed
    args.max_years = None # Default if not parsed
    args.perform_planning_phase = False # Default if not parsed
    args.num_negotiation_rounds = 0 # Default if not parsed
    args.negotiation_style = "simultaneous" # Default if not parsed
    args.randomize_fixed_models = False # Default if not parsed
    # args.dev_mode is already set by parse_arguments

    config = GameConfig(args) # GameConfig now gets args including use_mocks and dev_mode
    
    setup_logging(config)
    
    logger.info(f"🧪 Starting Diplomacy game test: {config.game_id} (Mocks: {args.use_mocks})")
    logger.info(f"Test type: {args.test_type}")
    logger.info(f"Test powers: {test_powers}")
    logger.info(f"Model IDs: {args.model_ids}")
    
    start_time = time.time()
    final_success = False
    
    try:
        tester = GameTester(config) # Pass the config object
        await tester.setup_game()
        
        if args.test_type == "single_round":
            final_success = await tester.test_single_round(test_powers)
        elif args.test_type == "order_generation":
            if test_powers:
                # For order_generation, initialize only the first agent
                power_to_test = test_powers[0]
                model_for_single_test = args.fixed_models[0] # Get its assigned model
                tester.agent_manager.initialize_agents({power_to_test: model_for_single_test})
                final_success = await tester.test_power_order_generation(power_to_test)
        elif args.test_type == "sequential_calls":
            if test_powers:
                final_success = await tester.test_sequential_calls(test_powers[0], args.num_sequential)
        elif args.test_type == "concurrent_calls":
            final_success = await tester.test_concurrent_calls(test_powers, args.max_concurrent)
        
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f"\n{'='*50}")
        logger.info("🏁 TEST COMPLETE")
        logger.info(f"{'='*50}")
        logger.info(f"Test type: {args.test_type}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: {'✅ SUCCESS' if final_success else '❌ FAILED'}")
        logger.info(f"Log directory: {config.game_id_specific_log_dir}")
        
        if final_success:
            logger.info("🎉 Test passed!")
        else:
            logger.error("💥 Test failed. Check logs for details.")
        
        sys.exit(0 if final_success else 1)
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user (KeyboardInterrupt)")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed with unexpected error: {e}", exc_info=True)
        detailed_error = traceback.format_exc()
        logger.error(f"Detailed traceback:\n{detailed_error}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())