import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
# SimpleNamespace is no longer needed here as it's encapsulated in FakeGame in _diplomacy_fakes.py
# from types import SimpleNamespace 

from ai_diplomacy.orchestrators.movement import MovementPhaseStrategy
from tests._diplomacy_fakes import FakeGame, DummyOrchestrator

@pytest.mark.asyncio
async def test_movement_generates_orders(mocker):
    strat = MovementPhaseStrategy()
    powers = ["ENG", "FRA"]
    fake_game = FakeGame("S1901M", powers)
    
    # Mock dependencies for DummyOrchestrator
    mock_game_config = MagicMock()
    # mock_game_config.llm_log_path = "/tmp/dummy_log_path" # If using get_valid_orders_func
    mock_game_config.num_negotiation_rounds = 1 # For perform_negotiation_rounds

    mock_agent_manager = MagicMock()
    # Simplistic agent mock for _get_orders_for_power to function if it checks agent type
    mock_agent = MagicMock()
    mock_agent_manager.get_agent.return_value = mock_agent

    dummy_orchestrator = DummyOrchestrator(powers, mock_game_config, mock_agent_manager)

    # Mock GameHistory (passed to strategy's get_orders)
    mock_game_history = MagicMock()
    mock_game_history.add_orders = MagicMock() # Called by the strategy
    mock_game_history.add_phase = MagicMock() # Called by perform_negotiation_rounds
    mock_game_history.add_message = MagicMock() # Called by perform_negotiation_rounds

    # Patch external calls made by MovementPhaseStrategy or its helpers
    # perform_negotiation_rounds is now a separate function imported by movement.py
    mocked_perform_negotiation = mocker.patch(
        "ai_diplomacy.orchestrators.movement.perform_negotiation_rounds", 
        new_callable=AsyncMock, 
        return_value=None
    )
    # _get_orders_for_power is a method on the orchestrator, already mocked in DummyOrchestrator
    # gather_possible_orders is used by orchestrator._get_orders_for_power for non-LLM agents
    # For this test, _get_orders_for_power on DummyOrchestrator is an AsyncMock, so gather_possible_orders won't be hit
    # unless we were testing the non-LLM path of _get_orders_for_power itself.
    # mocker.patch("ai_diplomacy.utils.gather_possible_orders", return_value={"A LON": ["A LON H"]})

    orders = await strat.get_orders(fake_game, dummy_orchestrator, mock_game_history)

    # Assertions
    mocked_perform_negotiation.assert_awaited_once_with(
        fake_game, mock_game_history, dummy_orchestrator.agent_manager, 
        dummy_orchestrator.active_powers, dummy_orchestrator.config
    )
    
    # Check that _get_orders_for_power was called for each active power
    assert dummy_orchestrator._get_orders_for_power.await_count == len(powers)
    for power_name in powers:
        # Check if _get_orders_for_power was called with this power_name
        # This is a bit tricky as it's called multiple times. 
        # We can check call_args_list
        power_found_in_calls = False
        for call in dummy_orchestrator._get_orders_for_power.call_args_list:
            args, _ = call
            if args[1] == power_name: # game, power_name, agent, game_history
                power_found_in_calls = True
                break
        assert power_found_in_calls, f"_get_orders_for_power not called for {power_name}"

    # Check that game_history.add_orders was called for each power
    assert mock_game_history.add_orders.call_count == len(powers)
    for power_name in powers:
        # Check if add_orders was called correctly
        # Example: mock_game_history.add_orders.assert_any_call(fake_game.get_current_phase(), power_name, ["WAIVE"])
        # This depends on the exact orders returned by the mocked _get_orders_for_power
        # Since _get_orders_for_power is mocked on DummyOrchestrator to return ["WAIVE"], 
        # and this return is used by the strategy directly.
        power_order_added = False
        for call in mock_game_history.add_orders.call_args_list:
            args, _ = call
            if args[0] == fake_game.get_current_phase() and args[1] == power_name and args[2] == ["WAIVE"]:
                power_order_added = True
                break
        assert power_order_added, f"game_history.add_orders not called correctly for {power_name}"

    # Validate the structure of returned orders
    assert isinstance(orders, dict)
    assert set(orders.keys()) == set(powers)
    for power_name in powers:
        assert orders[power_name] == ["WAIVE"] # Based on DummyOrchestrator's _get_orders_for_power mock

