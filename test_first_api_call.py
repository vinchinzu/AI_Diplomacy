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

import dotenv
from diplomacy import Game

# Import our AI diplomacy components
from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.utils import get_valid_orders, gather_possible_orders

# Load environment variables
dotenv.load_dotenv()

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FirstAPICallTester:
    """Test class to validate the first API call and basic functionality."""
    
    def __init__(self, model_id: str = "gemma3:latest"):
        self.model_id = model_id
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
        
        args = TestArgs(self.model_id)
        self.config = GameConfig(args)
        
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
    
    async def test_first_api_call(self, power_name: str = "FRANCE"):
        """Test the first API call for order generation."""
        logger.info(f"Testing first API call for {power_name}...")
        
        try:
            if power_name not in self.agent_manager.agents:
                logger.error(f"❌ Agent for {power_name} not initialized")
                return False
                
            agent = self.agent_manager.agents[power_name]
            
            # Get current game state
            board_state = self.game.get_state()
            current_phase = self.game.current_short_phase
            
            # Get possible orders for this power
            possible_orders = gather_possible_orders(self.game, power_name)
            
            logger.info(f"Current phase: {current_phase}")
            logger.info(f"Possible orders for {power_name}: {possible_orders}")
            
            # Create a simple log file path
            log_file_path = os.path.join(self.config.game_id_specific_log_dir, "test_api_calls.csv")
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            
            # Test the API call
            model_error_stats = {}
            
            logger.info(f"🚀 Making first API call to {self.model_id} for {power_name}...")
            start_time = time.time()
            
            orders = await get_valid_orders(
                game=self.game,
                model_id=self.model_id,
                agent_system_prompt=agent.system_prompt,
                board_state=board_state,
                power_name=power_name,
                possible_orders=possible_orders,
                game_history=self.game_history,
                model_error_stats=model_error_stats,
                agent_goals=agent.goals,
                agent_relationships=agent.relationships,
                agent_private_diary_str=agent.format_private_diary_for_prompt(),
                log_file_path=log_file_path,
                phase=current_phase
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            logger.info(f"✅ API call completed in {duration:.2f} seconds")
            logger.info(f"Generated orders: {orders}")
            logger.info(f"Model error stats: {model_error_stats}")
            
            # Validate orders
            if orders and len(orders) > 0:
                logger.info(f"✅ Successfully generated {len(orders)} orders")
                for i, order in enumerate(orders):
                    logger.info(f"   Order {i+1}: {order}")
                return True
            else:
                logger.warning(f"⚠️  No orders generated (might be fallback)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during API call test: {e}", exc_info=True)
            return False
    
    async def test_multiple_sequential_calls(self, power_name: str = "FRANCE", num_calls: int = 3):
        """Test multiple sequential API calls to check for consistency."""
        logger.info(f"Testing {num_calls} sequential API calls for {power_name}...")
        
        success_count = 0
        
        for i in range(num_calls):
            logger.info(f"--- API Call {i+1}/{num_calls} ---")
            
            try:
                success = await self.test_first_api_call(power_name)
                if success:
                    success_count += 1
                    logger.info(f"✅ Call {i+1} succeeded")
                else:
                    logger.warning(f"⚠️  Call {i+1} failed")
                    
                # Small delay between calls
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Call {i+1} threw exception: {e}")
        
        success_rate = (success_count / num_calls) * 100
        logger.info(f"📊 Sequential test results: {success_count}/{num_calls} successful ({success_rate:.1f}%)")
        
        return success_count == num_calls
    
    async def test_concurrent_calls(self, powers: List[str] = ["FRANCE", "GERMANY"], max_concurrent: int = 2):
        """Test concurrent API calls to check for race conditions."""
        logger.info(f"Testing concurrent API calls for powers: {powers}")
        
        # Initialize all test powers
        for power in powers:
            success = await self.test_single_power_initialization(power)
            if not success:
                logger.error(f"❌ Failed to initialize {power} for concurrent test")
                return False
        
        # Create concurrent tasks
        tasks = []
        for power in powers[:max_concurrent]:
            task = asyncio.create_task(self.test_first_api_call(power))
            tasks.append((power, task))
        
        logger.info(f"🚀 Starting {len(tasks)} concurrent API calls...")
        start_time = time.time()
        
        # Wait for all tasks
        results = {}
        for power, task in tasks:
            try:
                result = await task
                results[power] = result
                logger.info(f"✅ {power}: {'Success' if result else 'Failed'}")
            except Exception as e:
                logger.error(f"❌ {power}: Exception - {e}")
                results[power] = False
        
        end_time = time.time()
        duration = end_time - start_time
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        logger.info(f"📊 Concurrent test results: {success_count}/{total_count} successful in {duration:.2f}s")
        
        return success_count == total_count
    
    async def run_all_tests(self):
        """Run all tests in sequence."""
        logger.info("🧪 Starting comprehensive API call tests...")
        
        test_results = {}
        
        # Test 1: Environment setup
        logger.info("\n=== Test 1: Environment Setup ===")
        await self.setup_test_environment()
        test_results["setup"] = True
        
        # Test 2: Single power initialization
        logger.info("\n=== Test 2: Single Power Initialization ===")
        test_results["initialization"] = await self.test_single_power_initialization()
        
        # Test 3: First API call
        logger.info("\n=== Test 3: First API Call ===")
        test_results["first_api_call"] = await self.test_first_api_call()
        
        # Test 4: Sequential calls
        logger.info("\n=== Test 4: Sequential API Calls ===")
        test_results["sequential_calls"] = await self.test_multiple_sequential_calls()
        
        # Test 5: Concurrent calls (only if sequential works)
        if test_results["sequential_calls"]:
            logger.info("\n=== Test 5: Concurrent API Calls ===")
            test_results["concurrent_calls"] = await self.test_concurrent_calls()
        else:
            logger.warning("⚠️  Skipping concurrent test due to sequential failures")
            test_results["concurrent_calls"] = False
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("🏁 TEST SUMMARY")
        logger.info("="*50)
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
        
        total_tests = len(test_results)
        passed_tests = sum(1 for result in test_results.values() if result)
        
        logger.info(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            logger.info("🎉 All tests passed! API calls are working correctly.")
        else:
            logger.error("💥 Some tests failed. Check the logs above for details.")
        
        return passed_tests == total_tests

async def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test first API call functionality")
    parser.add_argument("--model", default="gemma3:latest", help="Model ID to test")
    parser.add_argument("--power", default="FRANCE", help="Power to test")
    parser.add_argument("--test", choices=["all", "single", "sequential", "concurrent"], 
                       default="all", help="Which test to run")
    
    args = parser.parse_args()
    
    tester = FirstAPICallTester(model_id=args.model)
    
    try:
        if args.test == "all":
            success = await tester.run_all_tests()
        elif args.test == "single":
            await tester.setup_test_environment()
            await tester.test_single_power_initialization(args.power)
            success = await tester.test_first_api_call(args.power)
        elif args.test == "sequential":
            await tester.setup_test_environment()
            await tester.test_single_power_initialization(args.power)
            success = await tester.test_multiple_sequential_calls(args.power)
        elif args.test == "concurrent":
            await tester.setup_test_environment()
            success = await tester.test_concurrent_calls()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 