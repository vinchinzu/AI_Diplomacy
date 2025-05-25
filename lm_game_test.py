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
from typing import Dict, List, Optional

import dotenv
from diplomacy import Game

# New refactored components
from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.game_orchestrator import GamePhaseOrchestrator
from ai_diplomacy.game_results import GameResultsProcessor
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.utils import get_valid_orders, gather_possible_orders

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
        "--model_id", type=str, default="gemma3:latest",
        help="Model ID for the primary power's LLM. Default: gemma3:latest"
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

    return parser.parse_args()

class GameTester:
    """Test class for stepping through game functionality."""
    
    def __init__(self, config: GameConfig):
        self.config = config
        self.game = None
        self.game_history = None
        self.agent_manager = None
        
    async def setup_game(self):
        """Set up the game environment."""
        logger.info("Setting up test game environment...")
        
        # Create game and history
        self.game = Game()
        self.game_history = GameHistory()
        
        # Initialize agent manager
        self.agent_manager = AgentManager(self.config)
        
        logger.info(f"Game setup complete. Current phase: {self.game.current_short_phase}")
        
    async def test_single_round(self, test_powers: List[str]):
        """Test a single round of order generation."""
        logger.info(f"Testing single round for powers: {test_powers}")
        
        # Initialize agents for test powers
        powers_and_models = {}
        for power in test_powers:
            powers_and_models[power] = self.config.args.model_id
            
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
    
    async def test_power_order_generation(self, power_name: str) -> bool:
        """Test order generation for a specific power."""
        try:
            agent = self.agent_manager.agents[power_name]
            
            # Get current game state
            board_state = self.game.get_state()
            current_phase = self.game.current_short_phase
            
            # Get possible orders
            possible_orders = gather_possible_orders(self.game, power_name)
            
            logger.info(f"Current phase: {current_phase}")
            logger.info(f"Possible orders for {power_name}: {list(possible_orders.keys())}")
            
            # Create log file path
            log_file_path = os.path.join(self.config.game_id_specific_log_dir, "test_orders.csv")
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            
            # Generate orders
            model_error_stats = {}
            
            logger.info(f"🚀 Generating orders for {power_name}...")
            start_time = time.time()
            
            orders = await get_valid_orders(
                game=self.game,
                model_id=agent.model_id,
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
            
            logger.info(f"⏱️  Order generation took {duration:.2f} seconds")
            logger.info(f"📋 Generated orders: {orders}")
            logger.info(f"📊 Model error stats: {model_error_stats}")
            
            # Validate orders
            if orders and len(orders) > 0:
                logger.info(f"✅ Successfully generated {len(orders)} orders for {power_name}")
                for i, order in enumerate(orders):
                    logger.info(f"   Order {i+1}: {order}")
                return True
            else:
                logger.warning(f"⚠️  No orders generated for {power_name} (might be fallback)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during order generation for {power_name}: {e}", exc_info=True)
            return False
    
    async def test_sequential_calls(self, power_name: str, num_calls: int):
        """Test multiple sequential API calls."""
        logger.info(f"Testing {num_calls} sequential calls for {power_name}")
        
        # Initialize single agent
        powers_and_models = {power_name: self.config.args.model_id}
        self.agent_manager.initialize_agents(powers_and_models)
        
        if power_name not in self.agent_manager.agents:
            logger.error(f"❌ Failed to initialize agent for {power_name}")
            return False
        
        success_count = 0
        
        for i in range(num_calls):
            logger.info(f"\n--- Sequential Call {i+1}/{num_calls} ---")
            
            try:
                success = await self.test_power_order_generation(power_name)
                if success:
                    success_count += 1
                    logger.info(f"✅ Call {i+1} succeeded")
                else:
                    logger.warning(f"⚠️  Call {i+1} failed")
                
                # Small delay between calls
                if i < num_calls - 1:  # Don't delay after last call
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Call {i+1} threw exception: {e}")
        
        success_rate = (success_count / num_calls) * 100
        logger.info(f"\n📊 Sequential test results: {success_count}/{num_calls} successful ({success_rate:.1f}%)")
        
        return success_count == num_calls
    
    async def test_concurrent_calls(self, test_powers: List[str], max_concurrent: int):
        """Test concurrent API calls."""
        logger.info(f"Testing concurrent calls for powers: {test_powers[:max_concurrent]}")
        
        # Initialize agents for all test powers
        powers_and_models = {}
        for power in test_powers[:max_concurrent]:
            powers_and_models[power] = self.config.args.model_id
            
        self.agent_manager.initialize_agents(powers_and_models)
        
        # Verify all agents initialized
        for power in test_powers[:max_concurrent]:
            if power not in self.agent_manager.agents:
                logger.error(f"❌ Failed to initialize agent for {power}")
                return False
        
        # Create concurrent tasks
        tasks = []
        for power in test_powers[:max_concurrent]:
            task = asyncio.create_task(self.test_power_order_generation(power))
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
        
        logger.info(f"\n📊 Concurrent test results: {success_count}/{total_count} successful in {duration:.2f}s")
        
        return success_count == total_count

async def main():
    args = parse_arguments()
    
    # Parse test powers
    test_powers = [p.strip().upper() for p in args.test_powers.split(',')]
    
    # Create config
    args.fixed_models = [args.model_id] * len(test_powers)
    args.exclude_powers = None
    args.max_years = None
    args.perform_planning_phase = False
    args.num_negotiation_rounds = 0
    args.negotiation_style = "simultaneous"
    args.randomize_fixed_models = False
    args.game_id = f"{args.game_id_prefix}_{int(time.time())}"
    
    config = GameConfig(args)
    
    # Setup logging
    setup_logging(config)
    
    logger.info(f"🧪 Starting Diplomacy game test: {config.game_id}")
    logger.info(f"Test type: {args.test_type}")
    logger.info(f"Test powers: {test_powers}")
    logger.info(f"Model ID: {args.model_id}")
    
    start_time = time.time()
    
    try:
        # Create tester
        tester = GameTester(config)
        await tester.setup_game()
        
        # Run the specified test
        success = False
        
        if args.test_type == "single_round":
            success = await tester.test_single_round(test_powers)
            
        elif args.test_type == "order_generation":
            # Test just order generation for first power
            if test_powers:
                powers_and_models = {test_powers[0]: args.model_id}
                tester.agent_manager.initialize_agents(powers_and_models)
                success = await tester.test_power_order_generation(test_powers[0])
            
        elif args.test_type == "sequential_calls":
            if test_powers:
                success = await tester.test_sequential_calls(test_powers[0], args.num_sequential)
                
        elif args.test_type == "concurrent_calls":
            success = await tester.test_concurrent_calls(test_powers, args.max_concurrent)
        
        # Results
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f"\n{'='*50}")
        logger.info(f"🏁 TEST COMPLETE")
        logger.info(f"{'='*50}")
        logger.info(f"Test type: {args.test_type}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
        logger.info(f"Log directory: {config.game_id_specific_log_dir}")
        
        if success:
            logger.info("🎉 Test passed! API calls are working correctly.")
        else:
            logger.error("💥 Test failed. Check the logs above for details.")
        
        sys.exit(0 if success else 1)
        
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