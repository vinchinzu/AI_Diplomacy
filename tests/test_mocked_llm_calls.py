import asyncio
import pytest
from unittest.mock import patch, MagicMock

# AgentLLMInterface was removed in refactor
from ai_diplomacy.game_config import GameConfig
from diplomacy import Game
from ai_diplomacy.game_history import GameHistory
from ai_diplomacy.agents.base import BaseAgent
from ai_diplomacy.agents.llm_agent import LLMAgent
from ai_diplomacy.general_utils import (
    gather_possible_orders,
    get_valid_orders,
)  # Step 1: Import get_valid_orders and gather_possible_orders


# Helper class for configuration, can be defined at module level
class TestArgs:
    __test__ = False  # Prevent pytest from collecting this as a test class

    def __init__(self):
        self.power_name = "FRANCE"
        self.model_ids = ["test_model"]
        self.num_players = 1
        self.game_id_prefix = "test_mock"
        self.game_id = "test_mock_123"
        self.log_level = "INFO"
        self.log_to_file = False
        self.log_dir = "./mock_test_logs"
        self.perform_planning_phase = False
        self.num_negotiation_rounds = 0
        self.negotiation_style = "simultaneous"
        self.fixed_models = ["test_model"]
        self.randomize_fixed_models = False
        self.exclude_powers = None
        self.max_years = None
        self.test_powers = "FRANCE"


@pytest.fixture
def common_mocks():
    args = TestArgs()
    config = GameConfig(args)  # type: ignore

    game = Game()
    # game.phase = "S1901M" # Set phase directly - this is usually handled by game processing
    # For tests, it's better to ensure the game object is in the expected state.
    # If get_all_possible_orders or other methods depend on phase, ensure it's set.
    # However, diplomacy.Game() starts in S1901M by default.

    game_history = MagicMock(spec=GameHistory)
    # Removed obsolete mock setups for methods not on GameHistory spec or not used by current SUT
    # game_history.get_event_log_for_power.return_value = "Fake history log"
    # game_history.get_full_event_log.return_value = "Fake full history log"
    game_history.get_messages_this_round.return_value = "Fake messages for this round"

    # agent_interface is None in the original setup for these tests
    return {
        "game": game,
        "game_history": game_history,
        "config": config,
        "power_name": "FRANCE",  # Default power for these tests
    }


# Commented out tests related to AgentLLMInterface as they were disabled
# @patch('ai_diplomacy.llm_coordinator.LocalLLMCoordinator.llm_call_internal')
# @pytest.mark.asyncio
# async def test_mock_agent_negotiation_diary_success(mock_llm_call_internal, common_mocks):
#     # This test is disabled because AgentLLMInterface was removed in refactor
#     pass

# @patch('ai_diplomacy.llm_coordinator.LocalLLMCoordinator.llm_call_internal')
# @pytest.mark.asyncio
# async def test_mock_agent_negotiation_diary_json_fail(mock_llm_call_internal, common_mocks):
#     # This test is disabled because AgentLLMInterface was removed in refactor
#     pass


@pytest.mark.asyncio
@patch("ai_diplomacy.services.llm_coordinator.llm_call_internal")
async def test_mock_get_valid_orders_success(mock_llm_call_internal, common_mocks):
    game = common_mocks["game"]
    game_history = common_mocks["game_history"]
    config = common_mocks["config"]
    power_name = common_mocks["power_name"]

    # Units for FRANCE in S1901M: A PAR, A MAR, F BRE
    game.set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
    # Ensure game phase is S1901M for get_all_possible_orders to be accurate
    # game.phase = "S1901M" # diplomacy.Game() starts in S1901M

    # Use power-specific possible orders
    power_specific_possible_orders = gather_possible_orders(game, power_name)

    mock_response_json_string = '{"orders": ["A PAR H", "A MAR H", "F BRE H"]}'
    # llm_call_internal is async, so its mock should be awaitable or return an awaitable
    # Patch creates a MagicMock. If its return_value is set to a future, it works.
    # Or, if return_value is a direct value, it should be fine if the mock is treated as awaitable.
    # For clarity with async functions, AsyncMock is often preferred, but MagicMock can work.
    fut = asyncio.Future()
    fut.set_result(mock_response_json_string)
    mock_llm_call_internal.return_value = fut

    orders = await get_valid_orders(
        game=game,
        model_id="test_model",
        agent_system_prompt="System prompt for FRANCE",
        board_state=game.get_state(),  # board_state is phase dependent
        power_name=power_name,
        possible_orders=power_specific_possible_orders,  # Use power-specific
        game_history=game_history,
        game_id=config.game_id,
        config=config,
        agent_goals=["Goal 1"],
        agent_relationships={"GERMANY": "Neutral"},
        log_file_path="./mock_test_logs/orders.csv",  # Consider using tmp_path fixture for logs
        phase=game.phase,  # Use game.phase
    )

    mock_llm_call_internal.assert_called_once()
    # Sort both lists for comparison as order is not guaranteed
    assert sorted(orders) == sorted(["A PAR H", "A MAR H", "F BRE H"])


@pytest.mark.asyncio
@patch("ai_diplomacy.services.llm_coordinator.llm_call_internal")
async def test_mock_get_valid_orders_json_fail(mock_llm_call_internal, common_mocks):
    game = common_mocks["game"]
    game_history = common_mocks["game_history"]
    config = common_mocks["config"]
    power_name = common_mocks["power_name"]

    game.set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
    # game.phase = "S1901M"

    # Use power-specific possible orders
    power_specific_possible_orders = gather_possible_orders(game, power_name)

    # expected_fallback_orders should be calculated based on these power_specific_possible_orders
    expected_fallback_orders = []
    for loc_str_key in power_specific_possible_orders:  # loc_str_key is like "A PAR"
        orders_for_loc = power_specific_possible_orders[loc_str_key]
        # unit_type = loc_str_key.split()[0] # Not needed if using holds[0] or orders_for_loc[0]
        # unit_loc_name = loc_str_key.split()[1]
        hold_order_candidates = [o for o in orders_for_loc if o.endswith(" H")]

        if hold_order_candidates:
            expected_fallback_orders.append(hold_order_candidates[0])
        elif orders_for_loc:  # If no hold, take the first available order
            expected_fallback_orders.append(orders_for_loc[0])
    expected_fallback_orders.sort()

    mock_response_malformed_json_string = '{"orders": ["A PAR H", "A MAR H", "F BRE H"'
    fut = asyncio.Future()
    fut.set_result(mock_response_malformed_json_string)
    mock_llm_call_internal.return_value = fut

    orders = await get_valid_orders(
        game=game,
        model_id="test_model",
        agent_system_prompt="System prompt",
        board_state=game.get_state(),
        power_name=power_name,
        possible_orders=power_specific_possible_orders,  # Use power-specific
        game_history=game_history,
        game_id=config.game_id,
        config=config,
        phase=game.phase,
    )

    mock_llm_call_internal.assert_called_once()
    orders.sort()
    assert orders == expected_fallback_orders


@pytest.mark.asyncio
@patch("ai_diplomacy.services.llm_coordinator.llm_call_internal")
async def test_mock_get_valid_orders_empty_response(
    mock_llm_call_internal, common_mocks
):
    game = common_mocks["game"]
    game_history = common_mocks["game_history"]
    config = common_mocks["config"]
    power_name = common_mocks["power_name"]

    game.set_units("FRANCE", ["A PAR", "A MAR", "F BRE"])
    # game.phase = "S1901M"

    # Use power-specific possible orders
    power_specific_possible_orders = gather_possible_orders(game, power_name)

    # expected_fallback_orders should be calculated based on these power_specific_possible_orders
    expected_fallback_orders = []
    for loc_str_key in power_specific_possible_orders:  # loc_str_key is like "A PAR"
        orders_for_loc = power_specific_possible_orders[loc_str_key]
        hold_order_candidates = [o for o in orders_for_loc if o.endswith(" H")]

        if hold_order_candidates:
            expected_fallback_orders.append(hold_order_candidates[0])
        elif orders_for_loc:  # If no hold, take the first available order
            expected_fallback_orders.append(orders_for_loc[0])
    expected_fallback_orders.sort()

    mock_empty_response_string = ""
    fut = asyncio.Future()
    fut.set_result(mock_empty_response_string)
    mock_llm_call_internal.return_value = fut

    orders = await get_valid_orders(
        game=game,
        model_id="test_model",
        agent_system_prompt="System prompt",
        board_state=game.get_state(),
        power_name=power_name,
        possible_orders=power_specific_possible_orders,  # Use power-specific
        game_history=game_history,
        game_id=config.game_id,
        config=config,
        phase=game.phase,
    )

    mock_llm_call_internal.assert_called_once()
    orders.sort()
    assert orders == expected_fallback_orders


