#!/usr/bin/env python3
"""
Modified version of lm_game.py for testing first round functionality.
This allows stepping through just the first round to validate API calls.
"""

import asyncio
import logging
import os
import time
from typing import List, Optional
from unittest.mock import AsyncMock  # Added AsyncMock
import pytest
import json

import dotenv
from diplomacy import Game

# New refactored components
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.general_utils import (
    get_valid_orders,
    gather_possible_orders,
    LLMInvalidOutputError,
)
from ai_diplomacy.agents.base import PhaseState # Added import
from ai_diplomacy import constants as diplomacy_constants # Added import


# Use the shared factory for GameConfig
# from ._shared_fixtures import create_game_config # This should be from tests._shared_fixtures
from tests._shared_fixtures import create_game_config  # Corrected import
from ai_diplomacy.game_config import GameConfig


# Suppress warnings
os.environ["GRPC_PYTHON_LOG_LEVEL"] = "40"
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["ABSL_MIN_LOG_LEVEL"] = "2"
os.environ["GRPC_POLL_STRATEGY"] = "poll"

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

# Default model for live tests - MAKE SURE THIS IS A VALID, ACCESSIBLE MODEL
LIVE_MODEL_ID = "gemma3:latest"  # Or use an environment variable


def _prepare_config_for_test(
    execution_mode: str,
    test_powers_str: str,
    model_ids_str: Optional[str] = None,
    num_players: int = 1,
    num_sequential: int = 2,
    max_concurrent: int = 2,
    log_to_file_override: bool = True,
    log_dir_override: str = "logs/pytest_logs",
) -> GameConfig:
    """Helper function to create GameConfig for tests using the shared factory."""

    use_mocks = execution_mode == "mock"

    actual_model_ids_str: str
    if use_mocks:
        actual_model_ids_str = (
            model_ids_str if model_ids_str else "mock_model_1,mock_model_2"
        )
    else:
        actual_model_ids_str = model_ids_str if model_ids_str else LIVE_MODEL_ID
        num_test_powers = len(test_powers_str.split(","))
        if "," not in actual_model_ids_str and num_test_powers > 1:
            actual_model_ids_str = ",".join([LIVE_MODEL_ID] * num_test_powers)

    parsed_model_ids = [m.strip() for m in actual_model_ids_str.split(",")]
    test_powers_list = [p.strip().upper() for p in test_powers_str.split(",")]

    num_models = len(parsed_model_ids)
    fixed_models = [
        parsed_model_ids[i % num_models] if num_models > 0 else "default_mock_model"
        for i in range(len(test_powers_list))
    ]

    config_kwargs = {
        "use_mocks": use_mocks,
        "dev_mode": True,
        "game_id_prefix": f"pytest_{execution_mode}",
        "log_level": "INFO",
        "log_to_file": log_to_file_override,
        "log_dir": log_dir_override,
        "test_powers": test_powers_str,
        "model_ids": parsed_model_ids,
        "fixed_models": fixed_models,
        "num_players": num_players,
        "power_name": None,
        "game_id": f"pytest_{execution_mode}_{int(time.time())}",
        "exclude_powers": None,
        "max_years": 1,
        "perform_planning_phase": False,
        "num_negotiation_rounds": 0,
        "negotiation_style": "simultaneous",
        "randomize_fixed_models": False,
        "models_config_file": None,
    }

    config_kwargs["num_sequential"] = num_sequential
    config_kwargs["max_concurrent"] = max_concurrent

    config = create_game_config(**config_kwargs)
    setup_logging(config)
    return config


class GameTester:
    """Test class for stepping through game functionality."""

    def __init__(self, config: GameConfig):
        self.config = config
        self.game = None
        self.game_history = None
        self.agent_manager = None

    async def setup_game(self):
        """Set up the game environment."""
        logger.info(
            f"Setting up test game environment (Mocks: {self.config.args.use_mocks})..."
        )
        self.game = Game()
        self.game_history = GameHistory()
        self.agent_manager = AgentManager(self.config)
        logger.info(
            f"Game setup complete. Current phase: {self.game.current_short_phase}"
        )

    async def test_single_round(self, test_powers: List[str]):
        """Test a single round of order generation."""
        logger.info(
            f"Testing single round for powers: {test_powers} (Mocks: {self.config.args.use_mocks})"
        )
        powers_and_models = {}
        fixed_models_list = self.config.args.fixed_models
        for i, power in enumerate(test_powers):
            powers_and_models[power] = fixed_models_list[i]

        agent_configurations = {
            p_name: {"type": "llm", "model_id": m_id, "country": p_name}
            for p_name, m_id in powers_and_models.items()
        }
        self.agent_manager.initialize_agents(agent_configurations)
        if not self.agent_manager.agents:
            logger.error("❌ No agents were initialized")
            return False
        logger.info(f"✅ Initialized {len(self.agent_manager.agents)} agents")
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
                logger.error(
                    f"❌ {power_name}: Exception during test - {e}", exc_info=True
                )
        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
        logger.info(
            f"\n📊 Single round test results: {success_count}/{total_count} successful ({success_rate:.1f}%)"
        )
        return success_count == total_count

    async def _get_mocked_llm_call_internal(
        self, power_name_for_mock: str, *args, **kwargs
    ):
        pass # Add pass to fix indentation error
    async def test_power_order_generation(self, power_name: str) -> bool:
        """Tests order generation for a single power."""
        agent = self.agent_manager.get_agent(power_name)
        if not agent:
            logger.error(
                f"Agent for {power_name} not found during order generation test."
            )
            return False
        if not agent:
            logger.error(
                f"Agent for {power_name} not found during order generation test."
            )
            return False

        phase_state = PhaseState.from_game(self.game) # Create PhaseState
        logger.info(
            f"[{power_name}] Current phase for order generation: {phase_state.phase_name}"
        )
        # board_state and possible_orders are now encapsulated or handled within agent.decide_orders or its context prep

        logger.info(f"🚀 Generating orders for {power_name}...")
        start_time = time.time()

        orders = None
        try:
            if self.config.args.use_mocks:
                if hasattr(agent, "generic_agent") and agent.generic_agent is not None: # Check if LLMAgent
                    agent.generic_agent.decide_action = AsyncMock()

                    # Define mock orders based on power_name
                    mock_orders_db = {
                        "FRANCE": ["A PAR H", "A MAR H", "F BRE H"],
                        "GERMANY": ["A BER H", "A MUN H", "F KIE H"],
                        "ENGLAND": ["F LON H", "F EDI H", "A LVP H"],
                    }
                    selected_orders = mock_orders_db.get(
                        power_name, [f"A {power_name[:3].upper()} H"] # Default mock order
                    )
                    agent.generic_agent.decide_action.return_value = {
                        diplomacy_constants.LLM_RESPONSE_KEY_ORDERS: selected_orders
                    }
                else: # Fallback for non-LLM agents or if generic_agent is not set up as expected
                    logger.warning(f"Mocking not fully applied for {power_name} as it's not a standard LLMAgent or generic_agent is missing.")
                    # Potentially, could mock agent.decide_orders directly if it's an AsyncMock in a base class
                    # For now, it might proceed without specific mock orders for this type.
                    pass # Let it proceed, it might fail or return empty if not an LLM agent.

            orders = await agent.decide_orders(phase_state)

        except LLMInvalidOutputError as e: # This error might be raised by LLMAgent's _extract_orders_from_response
            logger.error(
                f"DEV_MODE: LLMInvalidOutputError for {power_name} ({agent.model_id if hasattr(agent, 'model_id') else 'N/A'}): {e}"
            )
            return False
        except Exception as e: # Catch other potential errors during decide_orders
            logger.error(
                f"Exception during decide_orders for {power_name}: {e}", exc_info=True
            )
            return False


        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"⏱️  Order generation for {power_name} took {duration:.2f} seconds")

        # Orders are now List[Order] objects
        order_strings = [str(o) for o in orders] if orders else []
        logger.info(f"📋 Generated orders for {power_name}: {order_strings}")

        if self.config.args.use_mocks and orders is not None:
            mock_db_strings = {
                "FRANCE": ["A PAR H", "A MAR H", "F BRE H"],
                "GERMANY": ["A BER H", "A MUN H", "F KIE H"],
                "ENGLAND": ["F LON H", "F EDI H", "A LVP H"],
            }
            expected_mocked_order_strings = mock_db_strings.get(
                power_name, [f"A {power_name[:3].upper()} H"]
            )
            # Compare list of strings
            assert sorted(order_strings) == sorted(expected_mocked_order_strings), (
                f"Mock orders mismatch for {power_name}: expected {expected_mocked_order_strings}, got {order_strings}"
            )

        if orders and len(orders) > 0:
            logger.info(
                f"✅ Successfully generated {len(orders)} orders for {power_name}"
            )
            return True
        else:
            logger.warning(f"⚠️  No orders generated for {power_name}")
            return False

    async def test_sequential_calls(self, power_name: str, num_calls: int):
        """Test multiple sequential API calls."""
        logger.info(
            f"Testing {num_calls} sequential calls for {power_name} (Mocks: {self.config.args.use_mocks})"
        )

        # Agent initialization is now expected to be handled by the calling test function's setup
        # or test_single_round if that's what sets up agents.
        # For this specific test, we ensure the agent for power_name is initialized.
        if power_name not in self.agent_manager.agents:
            # Attempt to initialize just this one agent if not already present
            logger.info(
                f"Agent for {power_name} not found, attempting initialization for sequential test."
            )
            try:
                original_test_powers = [
                    p.strip().upper() for p in self.config.args.test_powers.split(",")
                ]
                power_index = original_test_powers.index(power_name) # type: ignore
                model_to_use_for_power = self.config.args.fixed_models[power_index] # type: ignore
                agent_config_for_power = {
                    power_name: {"type": "llm", "model_id": model_to_use_for_power, "country": power_name}
                }
                self.agent_manager.initialize_agents(agent_config_for_power)
            except (ValueError, IndexError) as e:
                logger.error(
                    f"❌ Failed to determine model for {power_name} for sequential test: {e}"
                )
                return False

        if power_name not in self.agent_manager.agents:
            logger.error(
                f"❌ Failed to initialize agent for {power_name} for sequential test."
            )
            return False

        success_count = 0
        for i in range(num_calls):
            logger.info(f"\n--- Sequential Call {i + 1}/{num_calls} ---")
            success = await self.test_power_order_generation(power_name)
            if success:
                success_count += 1
                logger.info(f"✅ Call {i + 1} for {power_name} succeeded")
            else:
                logger.warning(f"⚠️  Call {i + 1} for {power_name} failed")
            if i < num_calls - 1:
                await asyncio.sleep(0.1 if self.config.args.use_mocks else 1)
        success_rate = (success_count / num_calls) * 100
        logger.info(
            f"\n📊 Sequential test results for {power_name}: {success_count}/{num_calls} successful ({success_rate:.1f}%)"
        )
        return success_count == num_calls

    async def test_concurrent_calls(self, test_powers: List[str], max_concurrent: int):
        """Test concurrent API calls."""
        # Agent initialization is expected to be handled by the calling test function's setup.
        # This method will operate on the agents already initialized in self.agent_manager.

        concurrent_powers_to_test = [
            p for p in test_powers if p in self.agent_manager.agents
        ][:max_concurrent]
        if not concurrent_powers_to_test:
            logger.error("❌ No agents available or initialized for concurrent test.")
            return False

        logger.info(
            f"Testing concurrent calls for powers: {concurrent_powers_to_test} (Mocks: {self.config.args.use_mocks})"
        )

        tasks = [
            asyncio.create_task(self.test_power_order_generation(p_name))
            for p_name in concurrent_powers_to_test
        ]
        logger.info(f"🚀 Starting {len(tasks)} concurrent API calls...")
        start_time = time.time()
        results_list = await asyncio.gather(*tasks)
        end_time = time.time()
        duration = end_time - start_time
        results_map = {
            power_name: result
            for power_name, result in zip(concurrent_powers_to_test, results_list)
        }
        for p_name, res in results_map.items():
            logger.info(
                f"🏁 Concurrent result for {p_name}: {'Success' if res else 'Failed'}"
            )
        success_count = sum(1 for res in results_list if res)
        total_count = len(concurrent_powers_to_test)
        logger.info(
            f"\n📊 Concurrent test results: {success_count}/{total_count} successful in {duration:.2f}s"
        )
        return success_count == total_count


# --- Pytest Test Functions ---


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "execution_mode", ["mock"]
)  # Temporarily disable live for focus
async def test_single_round_scenario(execution_mode, request: pytest.FixtureRequest):
    # if execution_mode == "live": # Integration marker removed as live mode is disabled here
    #     request.applymarker(pytest.mark.integration)

    test_powers_str = "FRANCE,GERMANY"
    # For live mode, ensure enough models are specified or use the default LIVE_MODEL_ID for all
    model_ids_str = (
        "mock_fr,mock_ge"
        if execution_mode == "mock"
        else f"{LIVE_MODEL_ID},{LIVE_MODEL_ID}"
    )

    config = _prepare_config_for_test(execution_mode, test_powers_str, model_ids_str)

    tester = GameTester(config)
    await (
        tester.setup_game()
    )  # Sets up agents based on config.args.test_powers and config.args.fixed_models

    # test_single_round expects a list of powers that are defined in config.args.test_powers
    # and have corresponding models in config.args.fixed_models
    # The setup_game initializes AgentManager, but test_single_round re-initializes agents
    # based on the test_powers list passed to it and models from config.args.fixed_models.
    # Ensure test_powers_list matches what fixed_models were set up for.
    test_powers_list = [p.strip().upper() for p in config.args.test_powers.split(",")]

    success = await tester.test_single_round(test_powers_list)
    assert success, f"Single round scenario failed in {execution_mode} mode."


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "execution_mode", ["mock"]
)  # Temporarily disable live for focus
async def test_order_generation_scenario(
    execution_mode, request: pytest.FixtureRequest
):
    # if execution_mode == "live": # Integration marker removed as live mode is disabled here
    #     request.applymarker(pytest.mark.integration)

    power_to_test = "FRANCE"
    model_id_str = "mock_fr_single" if execution_mode == "mock" else LIVE_MODEL_ID
    config = _prepare_config_for_test(execution_mode, power_to_test, model_id_str)

    tester = GameTester(config)
    await tester.setup_game()

    # Initialize agent for the single power to test
    # test_power_order_generation expects agent to be in agent_manager
    assert isinstance(
        tester.agent_manager, AgentManager
    )
    agent_config_for_power = {
        power_to_test: {"type": "llm", "model_id": config.args.fixed_models[0], "country": power_to_test}
    }
    tester.agent_manager.initialize_agents(agent_config_for_power)

    success = await tester.test_power_order_generation(power_to_test)
    assert success, (
        f"Order generation scenario for {power_to_test} failed in {execution_mode} mode."
    )


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "execution_mode", ["mock"]
)  # Temporarily disable live for focus
async def test_sequential_calls_scenario(
    execution_mode, request: pytest.FixtureRequest
):
    # if execution_mode == "live": # Integration marker removed as live mode is disabled here
    #     request.applymarker(pytest.mark.integration)

    power_to_test = "FRANCE"
    num_sequential_calls = 2  # Reduced for test speed
    model_id_str = "mock_fr_seq" if execution_mode == "mock" else LIVE_MODEL_ID
    config = _prepare_config_for_test(
        execution_mode, power_to_test, model_id_str, num_sequential=num_sequential_calls
    )

    tester = GameTester(config)
    await tester.setup_game()

    # Agent for power_to_test needs to be initialized.
    # The test_sequential_calls method itself re-initializes the agent.
    # So, ensuring config.args.test_powers and config.args.fixed_models are correctly set up by _prepare_config_for_test is key.

    success = await tester.test_sequential_calls(power_to_test, num_sequential_calls)
    assert success, (
        f"Sequential calls scenario for {power_to_test} failed in {execution_mode} mode."
    )


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "execution_mode", ["mock"]
)  # Temporarily disable live for focus
async def test_concurrent_calls_scenario(
    execution_mode, request: pytest.FixtureRequest
):
    # if execution_mode == "live": # Integration marker removed as live mode is disabled here
    #     request.applymarker(pytest.mark.integration)

    test_powers_str = "FRANCE,GERMANY"
    max_concurrent_calls = 2
    # For live mode, ensure enough models are specified or use the default LIVE_MODEL_ID for all
    model_ids_str = (
        "mock_fr_con,mock_ge_con"
        if execution_mode == "mock"
        else f"{LIVE_MODEL_ID},{LIVE_MODEL_ID}"
    )

    config = _prepare_config_for_test(
        execution_mode,
        test_powers_str,
        model_ids_str,
        max_concurrent=max_concurrent_calls,
    )

    tester = GameTester(config)
    await tester.setup_game()

    # test_concurrent_calls expects agents to be initialized.
    # It will select from agents already in tester.agent_manager.agents.
    # The AgentManager is initialized in setup_game using config.args.test_powers and config.args.fixed_models.
    # We need to ensure the agents for test_powers_str are initialized.

    powers_to_test_list = [p.strip().upper() for p in test_powers_str.split(",")]

    # Initialize agents that will be used in the concurrent test
    powers_and_models_for_concurrent = {}
    for i, power_name in enumerate(powers_to_test_list):
        powers_and_models_for_concurrent[power_name] = config.args.fixed_models[i] # type: ignore

    agent_configurations_for_concurrent = {
        p_name: {"type": "llm", "model_id": m_id, "country": p_name}
        for p_name, m_id in powers_and_models_for_concurrent.items()
    }
    assert isinstance(
        tester.agent_manager, AgentManager
    )
    tester.agent_manager.initialize_agents(agent_configurations_for_concurrent)

    success = await tester.test_concurrent_calls(
        powers_to_test_list, max_concurrent_calls
    )
    assert success, f"Concurrent calls scenario failed in {execution_mode} mode."
