#!/usr/bin/env python3
"""
Test script to validate the first API call and step through the first round.
This helps isolate and debug LLM connection issues without running a full game.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Dict, List
from unittest.mock import patch 

import dotenv
from diplomacy import Game

# Import our AI diplomacy components
from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.utils import get_valid_orders, gather_possible_orders
from ai_diplomacy.llm_coordinator import LLMCallResult # Added import

# Load environment variables
dotenv.load_dotenv()

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FirstAPICallTester:
    """Test class to validate the first API call and basic functionality."""
    
    def __init__(self, model_id: str = "gemma3:latest", use_mocks: bool = False): # Added use_mocks
        self.model_id = model_id
        self.use_mocks = use_mocks # Store use_mocks
        self.game = None
        self.game_history = None
        self.agent_manager = None
        self.config = None
        
    async def setup_test_environment(self):
        """Set up a minimal test environment."""
        logger.info("Setting up test environment...")
        
        # Create a minimal config for testing
        class TestArgs:
            def __init__(self, model_id):
                self.power_name = "FRANCE"
                self.model_id = model_id
                self.num_players = 1  # Just test one player
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
                # Add use_mocks to internal args for consistency if GameConfig needs it
                self.use_mocks = self.use_mocks 
        
        args = TestArgs(self.model_id)
        # Pass the actual args object from main to GameConfig if it's available
        # For now, ensure use_mocks is available on self.config.args
        if not hasattr(args, 'use_mocks'):
            args.use_mocks = self.use_mocks
        self.config = GameConfig(args)
        self.config.args.use_mocks = self.use_mocks # Ensure it's set on config.args
        
        # Setup logging
        setup_logging(self.config)
        
        # Create game and history
        self.game = Game()
        self.game_history = GameHistory()
        
        # Initialize agent manager with just one power
        self.agent_manager = AgentManager(self.config)
        
        logger.info(f"Test environment setup complete. Game ID: {self.config.game_id}")
        
    async def test_single_power_initialization(self, power_name: str = "FRANCE"):
        """Test initializing a single power."""
        logger.info(f"Testing initialization of power: {power_name}")
        
        try:
            # Assign model to single power
            powers_and_models = {power_name: self.model_id}
            self.agent_manager.initialize_agents(powers_and_models)
            
            if power_name in self.agent_manager.agents:
                agent = self.agent_manager.agents[power_name]
                logger.info(f"✅ Successfully initialized agent for {power_name}")
                logger.info(f"   Model ID: {agent.model_id}")
                logger.info(f"   Goals: {agent.goals}")
                logger.info(f"   Relationships: {agent.relationships}")
                return True
            else:
                logger.error(f"❌ Failed to initialize agent for {power_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during {power_name} initialization: {e}", exc_info=True)
            return False
    
    async def _get_mocked_llm_call_internal(self, *args, **kwargs):
        """Helper to provide a mocked llm_call_internal behavior."""
        future = asyncio.Future()
        # Default mock orders for FRANCE in S1901M
        # A PAR, A MAR, F BRE
        mock_response_json_string = '{"orders": ["A PAR H", "A MAR H", "F BRE H"]}'
        
        # Ensure the structure matches LLMCallResult
        mock_result = LLMCallResult(
            success=True,
            raw_response=mock_response_json_string,
            parsed_json={"orders": ["A PAR H", "A MAR H", "F BRE H"]},
            error_message=None,
            model_id=self.model_id, # Or a mock model_id
            prompt_text="mocked_prompt", # Dummy value
            system_prompt_text="mocked_system_prompt" # Dummy value
        )
        future.set_result(mock_result)
        return future

    async def test_first_api_call(self, power_name: str = "FRANCE"):
        """Test the first API call for order generation."""
        logger.info(f"Testing first API call for {power_name} (Mocks: {self.use_mocks})...")
        
        if power_name not in self.agent_manager.agents:
            logger.error(f"❌ Agent for {power_name} not initialized")
            return False
            
        agent = self.agent_manager.agents[power_name]
        
        # Get current game state
        self.game.set_phase("S1901M") # Ensure phase is set for possible orders
        # Example units for FRANCE in S1901M for consistent possible_orders
        # If game is fresh, it will be S1901M by default.
        # If not, ensure units are set for the power to get meaningful possible_orders
        if not self.game.get_units(power_name):
             if power_name == "FRANCE":
                 self.game.set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
             # Add other powers if needed for tests, or ensure game state is managed per test call
        
        board_state = self.game.get_state()
        current_phase = self.game.current_short_phase
        
        # Get possible orders for this power
        possible_orders = gather_possible_orders(self.game, power_name)
        
        logger.info(f"Current phase: {current_phase}")
        logger.info(f"Possible orders for {power_name}: {list(possible_orders.keys())}")
        
        # Create a simple log file path
        log_file_path = os.path.join(self.config.game_id_specific_log_dir, "test_api_calls.csv")
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        logger.info(f"🚀 Making first API call to {self.model_id} for {power_name}...")
        start_time = time.time()
        
        orders_callable = get_valid_orders(
            game=self.game,
            model_id=self.model_id,
            agent_system_prompt=agent.system_prompt,
            board_state=board_state,
            power_name=power_name,
            possible_orders=possible_orders,
            game_history=self.game_history,
            game_id=self.config.game_id,
            agent_goals=agent.goals,
            agent_relationships=agent.relationships,
            agent_private_diary_str=agent.format_private_diary_for_prompt(),
            log_file_path=log_file_path,
            phase=current_phase
        )

        orders = None
        if self.use_mocks:
            with patch('ai_diplomacy.llm_coordinator.LocalLLMCoordinator.llm_call_internal', 
                       side_effect=self._get_mocked_llm_call_internal):
                orders = await orders_callable
        else:
            orders = await orders_callable
            
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f"✅ API call completed in {duration:.2f} seconds")
        logger.info(f"Generated orders: {orders}")
        
        if self.use_mocks and orders is not None:
             # Example: FRANCE in S1901M has units A PAR, A MAR, F BRE
             # Fallback orders would be holds for these.
             # Mocked response is ["A PAR H", "A MAR H", "F BRE H"]
             self.assertEqual(orders, ["A PAR H", "A MAR H", "F BRE H"])

        # Validate orders
        if orders and len(orders) > 0:
            logger.info(f"✅ Successfully generated {len(orders)} orders")
            for i, order_item in enumerate(orders): # Renamed order to order_item to avoid conflict
                logger.info(f"   Order {i+1}: {order_item}")
            return True
        else:
            logger.warning(f"⚠️  No orders generated (might be fallback if not using mocks, or mock failed)")
            return False

    async def test_multiple_sequential_calls(self, power_name: str = "FRANCE", num_calls: int = 3):
        """Test multiple sequential API calls to check for consistency."""
        logger.info(f"Testing {num_calls} sequential API calls for {power_name} (Mocks: {self.use_mocks})...")
        
        success_count = 0
        for i in range(num_calls):
            logger.info(f"--- API Call {i+1}/{num_calls} ---")
            # test_first_api_call will internally use self.use_mocks
            success = await self.test_first_api_call(power_name)
            if success:
                success_count += 1
                logger.info(f"✅ Call {i+1} succeeded")
            else:
                logger.warning(f"⚠️  Call {i+1} failed")
            if i < num_calls -1: # Don't sleep after last call
                 await asyncio.sleep(0.1 if self.use_mocks else 1) # Shorter sleep for mocks
        
        success_rate = (success_count / num_calls) * 100
        logger.info(f"📊 Sequential test results: {success_count}/{num_calls} successful ({success_rate:.1f}%)")
        return success_count == num_calls
    
    async def test_concurrent_calls(self, powers: List[str] = ["FRANCE", "GERMANY"], max_concurrent: int = 2):
        """Test concurrent API calls to check for race conditions."""
        logger.info(f"Testing concurrent API calls for powers: {powers} (Mocks: {self.use_mocks})...")
        
        for power in powers: # Initialize all specified powers
            await self.test_single_power_initialization(power)
        
        tasks = []
        for power_idx, power_name in enumerate(powers[:max_concurrent]):
            # test_first_api_call will internally use self.use_mocks
            task = asyncio.create_task(self.test_first_api_call(power_name))
            tasks.append((power_name, task))
        
        logger.info(f"🚀 Starting {len(tasks)} concurrent API calls...")
        start_time = time.time()
        
        results = {}
        for power_name, task in tasks:
            results[power_name] = await task
            logger.info(f"✅ {power_name}: {'Success' if results[power_name] else 'Failed'}")
        
        end_time = time.time()
        duration = end_time - start_time
        success_count = sum(1 for res in results.values() if res)
        total_count = len(results)
        
        logger.info(f"📊 Concurrent test results: {success_count}/{total_count} successful in {duration:.2f}s")
        return success_count == total_count

    async def run_all_tests(self):
        """Run all tests in sequence. Mocking is handled by individual test methods based on self.use_mocks."""
        logger.info(f"🧪 Starting comprehensive API call tests (Mocks: {self.use_mocks})...")
        
        test_results = {}
        
        await self.setup_test_environment() # Setup is always needed
        test_results["setup"] = True
        
        test_results["initialization"] = await self.test_single_power_initialization()
        
        # The following tests will use self.use_mocks internally
        test_results["first_api_call"] = await self.test_first_api_call()
        test_results["sequential_calls"] = await self.test_multiple_sequential_calls()
        
        if test_results["sequential_calls"]: # Only run concurrent if sequential passes
            test_results["concurrent_calls"] = await self.test_concurrent_calls()
        else:
            logger.warning("⚠️  Skipping concurrent test due to sequential failures or mock setup issues.")
            test_results["concurrent_calls"] = False
            
        # Summary
        logger.info("\n" + "="*50)
        logger.info("🏁 TEST SUMMARY")
        logger.info("="*50)
        
        all_passed = True
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
            if not result:
                all_passed = False
        
        total_tests = len(test_results)
        passed_tests = sum(1 for result in test_results.values() if result)
        
        logger.info(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        
        if all_passed:
            logger.info("🎉 All tests passed! API calls are working correctly.")
        else:
            logger.error("💥 Some tests failed. Check the logs above for details.")
        
        return all_passed

async def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test first API call functionality")
    parser.add_argument("--model", default="gemma3:latest", help="Model ID to test (used if not mocking).")
    parser.add_argument("--power", default="FRANCE", help="Power to test.")
    parser.add_argument("--test", choices=["all", "single", "sequential", "concurrent"], 
                       default="all", help="Which test to run.")
    parser.add_argument("--use-mocks", action="store_true", default=False, 
                       help="Use mocked LLM responses instead of live calls.") # Added --use-mocks
    
    args = parser.parse_args()
    
    # Pass use_mocks to the tester
    tester = FirstAPICallTester(model_id=args.model, use_mocks=args.use_mocks)
    
    final_success = False
    try:
        if args.test == "all":
            final_success = await tester.run_all_tests()
        else: # For specific tests, setup_test_environment is needed first
            await tester.setup_test_environment()
            await tester.test_single_power_initialization(args.power) # Initialize the power
            if args.test == "single":
                final_success = await tester.test_first_api_call(args.power)
            elif args.test == "sequential":
                final_success = await tester.test_multiple_sequential_calls(args.power)
            elif args.test == "concurrent":
                # For concurrent, test_single_power_initialization should be called for all powers in the list by test_concurrent_calls
                # So, the above initialization for args.power is just for a single power context if needed.
                # test_concurrent_calls will handle its own power initializations.
                final_success = await tester.test_concurrent_calls() 
        
        sys.exit(0 if final_success else 1)
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())