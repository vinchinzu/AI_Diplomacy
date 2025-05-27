#!/usr/bin/env python3
"""
Modified version of lm_game.py for testing first round functionality.
This allows stepping through just the first round to validate API calls.
"""

import asyncio
import logging
import os
import time
from typing import List, Optional  # Added Any for mock args
from unittest.mock import patch
import pytest  # Added pytest
import json  # Added json import

import dotenv
from diplomacy import Game
from diplomacy.utils.export import to_saved_game_format

# New refactored components
from ai_diplomacy.game_config import GameConfig
from ai_diplomacy.logging_setup import setup_logging
from ai_diplomacy.agent_manager import AgentManager
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.general_utils import (
    get_state_value_from_search,
    get_order_value_from_search,
    gather_possible_orders,
    get_valid_orders,
    LLMInvalidOutputError,
)


# Suppress warnings
os.environ["GRPC_PYTHON_LOG_LEVEL"] = "40"
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["ABSL_MIN_LOG_LEVEL"] = "2"
os.environ["GRPC_POLL_STRATEGY"] = "poll"

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

# Default model for live tests - MAKE SURE THIS IS A VALID, ACCESSIBLE MODEL
LIVE_MODEL_ID = "gemma3:latest"  # Or use an environment variable


class MockArgs:
    """Helper class to simulate argparse.Namespace for GameConfig."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _prepare_config_for_test(
    execution_mode: str,
    test_powers_str: str,
    model_ids_str: Optional[str] = None,
    num_players: int = 1,
    num_sequential: int = 2,
    max_concurrent: int = 2,
) -> GameConfig:
    """Helper function to create GameConfig for tests."""

    use_mocks = execution_mode == "mock"

    # Determine model_ids based on execution_mode
    if use_mocks:
        # For mock mode, use placeholder model IDs that match what mock logic might expect
        # or simply ensure they are syntactically valid if not used by mock logic.
        actual_model_ids_str = (
            model_ids_str if model_ids_str else "mock_model_1,mock_model_2"
        )
    else:
        # For live mode, use the actual live model ID.
        # If specific models were passed for live, use them, otherwise default to LIVE_MODEL_ID.
        actual_model_ids_str = model_ids_str if model_ids_str else LIVE_MODEL_ID
        # Ensure all powers in live mode use a valid live model if multiple powers are tested
        num_test_powers = len(test_powers_str.split(","))
        if (
            "," not in actual_model_ids_str and num_test_powers > 1
        ):  # Only one model ID provided for multiple powers
            actual_model_ids_str = ",".join([LIVE_MODEL_ID] * num_test_powers)

    parsed_model_ids = [m.strip() for m in actual_model_ids_str.split(",")]

    test_powers_list = [p.strip().upper() for p in test_powers_str.split(",")]
    num_models = len(parsed_model_ids)
    fixed_models = [
        parsed_model_ids[i % num_models] for i in range(len(test_powers_list))
    ]

    args = MockArgs(
        use_mocks=use_mocks,
        dev_mode=True,  # Default from original script
        game_id_prefix=f"pytest_{execution_mode}",
        log_level="INFO",
        log_to_file=True,
        log_dir="./pytest_logs",
        test_powers=test_powers_str,
        model_ids=parsed_model_ids,  # Store as list
        fixed_models=fixed_models,
        num_players=num_players,
        num_sequential=num_sequential,
        max_concurrent=max_concurrent,
        # Defaults for other GameConfig fields not covered by original args
        power_name=None,  # From original args, default None
        game_id=f"pytest_{execution_mode}_{int(time.time())}",
        exclude_powers=None,
        max_years=None,
        perform_planning_phase=False,
        num_negotiation_rounds=0,
        negotiation_style="simultaneous",
        randomize_fixed_models=False,
    )

    config = GameConfig(args)  # type: ignore
    setup_logging(config)  # Setup logging for each test run based on its config
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
        self.agent_manager.initialize_agents(powers_and_models)
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
        """Helper to provide a mocked llm_call_internal behavior for a specific power."""
        mock_orders_db = {
            "FRANCE": ["A PAR H", "A MAR H", "F BRE H"],
            "GERMANY": ["A BER H", "A MUN H", "F KIE H"],
            "ENGLAND": ["F LON H", "F EDI H", "A LVP H"],
        }
        selected_orders = mock_orders_db.get(
            power_name_for_mock, [f"A {power_name_for_mock[:3].upper()} H"]
        )
        # Create a dictionary, then dump it to a JSON string.
        mock_orders_dict = {"orders": selected_orders}
        mock_response_json_string = json.dumps(mock_orders_dict)

        mock_full_response = f"Reasoning:\n- Mock reasoning for {power_name_for_mock}\n- These are test orders for validation\n\nPARSABLE OUTPUT:\n{mock_response_json_string}"
        return mock_full_response

    async def test_power_order_generation(self, power_name: str) -> bool:
        """Tests order generation for a single power."""
        agent = self.agent_manager.get_agent(power_name)
        if not agent:
            logger.error(
                f"Agent for {power_name} not found during order generation test."
            )
            return False
        current_phase = self.game.current_short_phase
        logger.info(
            f"[{power_name}] Current phase for order generation: {current_phase}"
        )
        board_state = self.game.get_state()
        possible_orders = gather_possible_orders(self.game, power_name)
        logger.info(f"Possible orders for {power_name}: {list(possible_orders.keys())}")
        log_file_path = os.path.join(
            self.config.game_id_specific_log_dir, "test_orders.csv"
        )
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        logger.info(f"🚀 Generating orders for {power_name}...")
        start_time = time.time()

        # Ensure agent.model_id, agent.system_prompt etc are correctly populated by AgentManager
        orders_callable = get_valid_orders(
            game=self.game,
            model_id=agent.model_id,
            agent_system_prompt=agent.system_prompt,
            board_state=board_state,
            power_name=power_name,
            possible_orders=possible_orders,
            game_history=self.game_history,
            game_id=self.config.game_id,
            config=self.config,
            agent_goals=agent.goals,
            agent_relationships=agent.relationships,
            agent_private_diary_str=agent.format_private_diary_for_prompt(),
            log_file_path=log_file_path,
            phase=current_phase,
        )
        orders = None
        try:
            if self.config.args.use_mocks:

                async def mock_side_effect(
                    *args_inner, **kwargs_inner
                ):  # Renamed args to avoid clash
                    return await self._get_mocked_llm_call_internal(
                        power_name, *args_inner, **kwargs_inner
                    )

                with patch(
                    "ai_diplomacy.services.llm_coordinator.llm_call_internal",
                    side_effect=mock_side_effect,
                ):
                    orders = await orders_callable
            else:
                orders = await orders_callable
        except LLMInvalidOutputError as e:
            logger.error(
                f"DEV_MODE: LLMInvalidOutputError for {power_name} ({agent.model_id}): {e}"
            )
            # Log details as before
            return False

        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"⏱️  Order generation for {power_name} took {duration:.2f} seconds")
        logger.info(f"📋 Generated orders for {power_name}: {orders}")

        if self.config.args.use_mocks and orders is not None:
            mock_db = {
                "FRANCE": ["A PAR H", "A MAR H", "F BRE H"],
                "GERMANY": ["A BER H", "A MUN H", "F KIE H"],
                "ENGLAND": ["F LON H", "F EDI H", "A LVP H"],
            }
            expected_mocked_orders = mock_db.get(
                power_name, [f"A {power_name[:3].upper()} H"]
            )
            assert sorted(orders) == sorted(expected_mocked_orders), (
                f"Mock orders mismatch for {power_name}: expected {expected_mocked_orders}, got {orders}"
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
                power_index = original_test_powers.index(power_name)
                model_to_use_for_power = self.config.args.fixed_models[power_index]
                self.agent_manager.initialize_agents(
                    {power_name: model_to_use_for_power}
                )
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
    )  # Ensure agent_manager is AgentManager
    tester.agent_manager.initialize_agents({power_to_test: config.args.fixed_models[0]})

    success = await tester.test_power_order_generation(power_to_test)
    assert success, (
        f"Order generation scenario for {power_to_test} failed in {execution_mode} mode."
    )


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
        powers_and_models_for_concurrent[power_name] = config.args.fixed_models[i]
    assert isinstance(
        tester.agent_manager, AgentManager
    )  # Ensure agent_manager is AgentManager
    tester.agent_manager.initialize_agents(powers_and_models_for_concurrent)

    success = await tester.test_concurrent_calls(
        powers_to_test_list, max_concurrent_calls
    )
    assert success, f"Concurrent calls scenario failed in {execution_mode} mode."
